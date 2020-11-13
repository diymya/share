#-*- coding:utf-8 -*-
import maya.cmds as mc
import maya.OpenMaya as om
import xgenm as xg
import xgenm.xgGlobal as xgg
import re,os,shutil
from CfxPipelineTool.pipeline.fun import alembicExport
'''
xgen 标签下的命令函数
'''

#/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
def setFrame(self):
    '''
    设置导出解算缓存的帧范围
    '''
    startFrame = self.pro.cfxStartFrame()
    endFrame = startFrame+50
    AlembicNode = mc.ls( fl=1, type='AlembicNode' )
    if AlembicNode:
        for i in AlembicNode:
            ef = round( mc.getAttr( '%s.endFrame'%(i) ) )
            if ef > endFrame:
                endFrame = ef
        self.spinBox_xgenSimStartFrame.setValue(startFrame)
        self.spinBox_xgenSimEndFrame.setValue(endFrame)
    else:
        startFrame = mc.playbackOptions( q=1, minTime=1 )
        endFrame = mc.playbackOptions( q=1, maxTime=1 )
        self.spinBox_xgenSimStartFrame.setValue(startFrame)
        self.spinBox_xgenSimEndFrame.setValue(endFrame)
#/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
def getSimulationCache(self):
    '''
    获取growMesh+simCurve反馈到导出ui上，根据用户操作执行导出；
    导出场景中的set，命名规则为 nameSpace:set_Sim；
    需要资产设置好set_Sim，set_Sim里面包含有growMesh和simCurve，不需要解算曲线的角色也要要有growMesh，为后面生成render文件做准备；
    导出路径为： 镜头ma文件路径/PipelineCache/xgen/chr（角色名）/ver/sim/ver/xxx.abc；
    如'shot/000/001/maya/PipelineCache/xgen/chr_lxy_new/v01/sim/v01/chr_lxy_new.abc'；
    '''
    # 判断场景保存状态
    maya_f = mc.file( q=1,sceneName=1 )
    if not maya_f:
        mc.warning( u'请打开 xgen Sim 文件执行' )
        return
    elif not maya_f[-3:] == '.ma':
        mc.warning( u'当前场景文件格式不符合规范，请保存为 ma 格式' )
        return
    maya_path = re.sub( r'/[^/]+\.ma$', '', maya_f, 0 )
    
    # 排除此类来历不明的nameSpace
    # Result: ('XG_RENDER_:chr_lxy_default:hair_lxy', 'xgen_chr_lxy_default:hair_lxy') # 
    # 获取xgen集合
    # 如果没有xgen警告并退出
    palettes = []
    for p in xg.palettes():
        if re.match( '^xgen_.+$', p ):
            palettes.append( p )
    if not palettes:
        mc.warning( u'未找到xgen集合' )
        return
    # 获取xgen的 simSetList
    # 如果没有则警告并退出
    simSetList = []
    for palette in palettes:
        nameSpace = re.sub( ':.*$', '', palette, 0 )
        simSet = '%s:set_Sim'%(nameSpace)
        if mc.ls( simSet, type='objectSet', fl=1 ):
            simSetList.append(simSet)
    if not simSetList:
        mc.warning( u'未找到set_Sim' )
        return
    '''
    # 这两个列表的index关联，patch对应xgDataPath
    # 获取xgen_patchs
    # 获取XgDataPaths文件夹路径
    xgen_patchs = []
    XgDataPaths = []
    for palette in palettes:
        xgen_patchs.append( maya_path + mc.getAttr( '%s.xgFileName'%(palette) ) )
    for xgen_patch in xgen_patchs:
        with open( xgen_patch,"r" ) as f:
            lines = f.readlines()
            for line in lines:
                if line[:13] == r'	xgDataPath		':
                    if r'${PROJECT}' in line:
                        mc.warning( u'当前资产文件 XgDataPath 不规范，不可以用相对路径 ${PROJECT} ！！' )
                        return
                    if ';' in line:
                        XgDataPath = re.sub( ';.+$', '', line[13:], 0 )
                    else:
                        XgDataPath = re.sub( r'\n$', '', line[13:], 0 )
                    XgDataPath = re.sub( r'\\', '/', XgDataPath, 0 )
                    XgDataPath = re.sub( '/$', '', XgDataPath, 0 )
                    XgDataPaths.append( XgDataPath )
                    break
    '''
    # 通过 simSetList 获取对应的 xgmPatch 及 xgmPatchXgData，生成字典
    # xgenCacheDict = { simSet:{ xgmPatch:xgmPatchXgData, ... }, ... }
    xgenCacheDict = {}
    for simSet in simSetList:
        nameSpace = re.sub( ':.*$', '', simSet )
        xgmPalettes = mc.ls( '%s:*'%(nameSpace), type='xgmPalette', fl=1 )
        if xgmPalettes:
            for xgmPalette in xgmPalettes:
                xgmPatch = '%s/%s'%(maya_path,mc.getAttr('%s.xgFileName'%(xgmPalette)))
                with open( xgmPatch,"r" ) as f:
                    lines = f.readlines()
                    xgmPatchXgData = ''
                    for line in lines:
                        if line[:13] == r'	xgDataPath		':
                            if r'${PROJECT}' in line:
                                mc.warning( u'当前资产文件 XgDataPath 不规范，不可以用相对路径 ${PROJECT} ！！' )
                                return
                            xgmPatchXgData = re.sub( r'\n$', '', line[13:] )
                            if ';' in xgmPatchXgData:
                                xgmPatchXgData = re.sub( ';.+$', '', xgmPatchXgData )
                            xgmPatchXgData = re.sub( r'\\', '/', xgmPatchXgData )
                            xgmPatchXgData = re.sub( '/$', '', xgmPatchXgData )
                            break
                    if xgmPatchXgData:
                        if not simSet in xgenCacheDict:
                            xgenCacheDict[simSet] = {xgmPatch:xgmPatchXgData}
                        else:
                            if not xgmPatch in xgenCacheDict[simSet]:
                                xgenCacheDict[simSet][xgmPatch] = xgmPatchXgData
    # print xgenCacheDict
    warningMessage = ''
    '''
    # 生成导出缓存列表
    # [ [ simSet, exportFile, [patch,...], [patch,...] ],... ]
    exportList = []
    for simSet in simSetList:
        matchA = re.sub( '^xgen_', '', simSet, 0 )
        matchA = re.sub( ':set_Sim$', '', matchA, 0 )
        exportFile = ''
        src_patchs = []
        dst_patchs = []
        for index,XgDataPath in enumerate(XgDataPaths):
            xgenCacheVer = re.sub( '/collections/[^/]+$', '', XgDataPath, 0 )
            message = re.sub( '^.*/maya', '', xgenCacheVer, 0 )
            xgenCacheVer = int( xgenCacheVer[-2:] )
            xgenCacheVerList = []
            xgenCacheVerPath = re.sub( '/v\d{2}/collections/[^/]+$', '', XgDataPath, 0 )
            for ver in os.listdir( xgenCacheVerPath ):
                if re.match( '^v\d{2}$', ver ):
                    xgenCacheVerList.append( int( ver[-2:] ) )
            if not xgenCacheVer == max( xgenCacheVerList ):
                warningMessage += '%s\n'%( message )
            matchB = re.sub( '/[^/]+$', '', XgDataPath, 0 )
            matchB = re.sub( '/[^/]+$', '', matchB, 0 )
            matchB = re.sub( '/[^/]+$', '', matchB, 0 )
            matchB = re.sub( '^.*/', '', matchB, 0 )
            if matchB == matchA:
                #索引并生成当前simVer迭代版本
                simVer = 'v01'
                simPath = re.sub( 'collections/[^/]+$', 'sim', XgDataPath, 0 )
                if os.path.exists(simPath):
                    simVerList = []
                    for i in os.listdir(simPath):
                        if os.path.isdir( '%s/%s'%(simPath,i) ) and re.match( '^v\d{2}$', i ):
                            simVerList.append( int( re.sub( '^v', '', i, 0 ) ) )
                    if simVerList:
                        simVer = 'v%02d'%( max(simVerList)+1 )
                #exportFile
                exportFile = re.sub( 'collections/[^/]+$', 'sim/%s/%s.abc'%(simVer,matchA), XgDataPath, 0 )
                src_patchs.append(xgen_patchs[index])
                dst_patch = re.sub( 'collections/[^/]+$', 'sim/%s/%s'%(simVer,re.sub('^.+/','',xgen_patchs[index],0)), XgDataPath, 0 )
                dst_patchs.append(dst_patch)
        if exportFile:
            exportList.append([simSet,exportFile,src_patchs,dst_patchs])
    
    # [ [ simSet, exportFile, [src_patch,...], [dst_patch,...] ],... ]
    print exportList
    for e in exportList:
        for i in mc.sets( e[0], q=1 ):
            print i
    '''
    # { 
    #   xgenCacheName:{ 'growMeshs':{'enabled':True,'objs':[growMesh,...]},
    #                   'simCurves':{ collection__description:{'enabled':True,'objs':[simCurve,...]}, ... },
    #                   'exportFile':exportFile,
    #                   'srcPatchs':[srcPatch,...],
    #                   'dstPatchs':[dstPatch,...] }
    # }
    exportDict = {}
    # xgenCacheDict = { simSet:{ xgmPatch:xgmPatchXgData, ... }, ... }
    for simSet in xgenCacheDict:
        nameSpace = re.sub( ':.*$', '', simSet )
        xgenCacheName = re.sub( '^xgen_', '', nameSpace, 0 )
        # key值
        growMeshs = {}
        simCurves = {}
        exportFile = ''
        srcPatchs = []
        dstPatchs = []
        objs = mc.sets( simSet, q=1 )
        if objs:
            for obj in objs:
                shapes = mc.listRelatives(obj, s=1)
                if shapes:
                    # 判断并放入 growMeshs
                    if mc.objectType(shapes[0]) == 'mesh':
                        if not 'objs' in growMeshs:
                            growMeshs['objs'] = [obj]
                            growMeshs['enabled'] = True
                        else:
                            growMeshs['objs'] += [obj]
                    elif mc.objectType(shapes[0]) == 'nurbsCurve':
                        objName = re.sub( '^.+:', '', obj )
                        objNameSplit = re.split('__',objName)
                        if len(objNameSplit)==4:
                            collection__description = '%s__%s'%(objNameSplit[0],objNameSplit[1])
                            if not collection__description in simCurves:
                                simCurves[collection__description] = {'enabled':True,'objs':[obj]}
                            else:
                                simCurves[collection__description]['objs'] += [obj]
        for xgmPatch in xgenCacheDict[simSet]:
            xgenCacheVerPath = re.sub( '/collections/[^/]+$', '', xgenCacheDict[simSet][xgmPatch] )
            currentVer =  int(re.sub( '^.+/v', '', xgenCacheVerPath ))
            message = re.sub( '^.*/maya', '', xgenCacheVerPath, 0 )
            xgenCachePath = re.sub( '/v\d{2}$', '', xgenCacheVerPath )
            if not os.path.exists(xgenCachePath):
                mc.warning( u'缓存指向路径 %s 不存在，检查文件再次尝试'%(xgenCachePath) )
                return
            # 判断当前xgen文件指向的缓存路径是否是最高版本，如果不是添加至 warningMessage
            verList = []
            for ver in os.listdir( xgenCachePath ):
                if re.match( '^v\d{2}$', ver ):
                    verList.append( int( ver[-2:] ) )
            if not currentVer == max( verList ):
                warningMessage += '%s\n'%( message )
            xgenCacheSimPath = '%s/sim'%(xgenCacheVerPath)
            simVer = 'v01'
            if os.path.exists(xgenCacheSimPath):
                simVerList = []
                for ver in os.listdir(xgenCacheSimPath):
                    if re.match( '^v\d{2}$', ver ):
                        simVerList.append( int( ver[-2:] ) )
                if simVerList:
                    simVer = 'v%02d'%( max(simVerList)+1 )
            simVerPath = '%s/%s'%(xgenCacheSimPath,simVer)
            exportFile = '%s/%s.abc'%(simVerPath,xgenCacheName)
            srcPatchs.append(xgmPatch)
            dstPatch = re.sub('^.+/','%s/'%(simVerPath),xgmPatch)
            dstPatchs.append(dstPatch)
        # print growMeshs
        # print simCurves
        # for k in simCurves:
        #     print k
        # print exportFile
        # print srcPatchs
        # print dstPatchs
        if exportFile and growMeshs:
            exportDict[xgenCacheName] = {'growMeshs':growMeshs,
                                            'simCurves':simCurves,
                                            'exportFile':exportFile,
                                            'srcPatchs':srcPatchs,
                                            'dstPatchs':dstPatchs}
    # # 警告
    # if warningMessage:
    #     enter = mc.confirmDialog( title='Warning', message=u'%s\n以上xgen缓存指向版本路径不是最新的，\n当前场景文件输出的 sim 缓存，\n在后续 Package 会识别不到，\n是否继续？'%(warningMessage),
    #                               button=['Yes','No'], defaultButton='Yes', cancelButton='No', dismissString='No' )
    #     if not enter =='Yes':
    #         return
    if warningMessage:
        from PySide2.QtWidgets import QMessageBox
        confirm = QMessageBox.question( self,
                                       u"Confirmation",
                                       u'%s\n以上xgen缓存指向版本路径不是最新的，\n当前场景文件输出的 sim 缓存，\n在后续 Package 会识别不到，\n是否继续？'%(warningMessage),
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes )
        if not confirm == QMessageBox.StandardButton.Yes:
            return
    if exportDict:
        self.launch_exportSimulationCaches(exportDict)
#/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
def exportSimulationCache(self,exportDict):
    '''
    导出growMesh+simCurve；
    导出场景中的set，命名规则为 nameSpace:set_Sim；
    需要资产设置好set_Sim，set_Sim里面包含有growMesh和simCurve，不需要解算曲线的角色也要要有growMesh，为后面生成render文件做准备；
    导出路径为： 镜头ma文件路径/PipelineCache/xgen/chr（角色名）/ver/sim/ver/xxx.abc；
    如'shot/000/001/maya/PipelineCache/xgen/chr_lxy_new/v01/sim/v01/chr_lxy_new.abc'；
    '''
    # 禁用显示
    mc.select(cl=1)
    for mp in mc.getPanel( type='modelPanel' ):
        mc.isolateSelect(mp,state=1) # 启用隔离显示，减轻gpu负担，提高cache速度
        # mc.modelEditor(mp,e=1,allObjects=0) # 关闭所有 modelPanel 的物体显示，减轻显示负担，提高cache速度
    
    # 导出解算缓存
    startTime = self.spinBox_xgenSimStartFrame.value()
    endTime = self.spinBox_xgenSimEndFrame.value()
    message = ''
    # { 
    #   xgenCacheName:{ 'growMeshs':{'enabled':True,'objs':[growMesh,...]},
    #                   'simCurves':{ collection__description:{'enabled':True,'objs':[simCurve,...]}, ... },
    #                   'exportFile':exportFile,
    #                   'srcPatchs':[srcPatch,...],
    #                   'dstPatchs':[dstPatch,...] }
    # }
    for xgenCacheName in exportDict:
        if exportDict[xgenCacheName]['growMeshs']['enabled']:
            exportFile = exportDict[xgenCacheName]['exportFile']
            path = re.sub( '/[^/]+$', '', exportFile )
            fileName = re.sub( '^.*/', '', exportFile, 0 )
            if not os.path.exists(path):
                os.makedirs(path)
            objs = exportDict[xgenCacheName]['growMeshs']['objs']
            for simCurves in exportDict[xgenCacheName]['simCurves']:
                if exportDict[xgenCacheName]['simCurves'][simCurves]['enabled']:
                    objs += exportDict[xgenCacheName]['simCurves'][simCurves]['objs']
            alembicExport( objs, exportFile, 1, startTime, endTime, 1 )
            for index,patch in enumerate(exportDict[xgenCacheName]['srcPatchs']):
                shutil.copyfile(patch,exportDict[xgenCacheName]['dstPatchs'][index])
            message += u'%s, '%(fileName)
    if message:
        mc.warning( u'%s 导出完成'%(message) )
    # 还原显示
    for mp in mc.getPanel( type='modelPanel' ):
        mc.isolateSelect(mp,state=0) # 启用隔离显示，减轻gpu负担，提高cache速度
    setCaches(self)
#/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
def setTimeSlider(self):
    '''
    根据场景内的AlembicNode设置帧范围
    '''
    startFrame = self.pro.cfxStartFrame()
    endFrame = startFrame+50
    AlembicNodes = mc.ls( fl=1, type='AlembicNode' )
    if AlembicNodes:
        for AlembicNode in AlembicNodes:
            sf = round( mc.getAttr( '%s.startFrame'%(AlembicNode) ) )
            ef = round( mc.getAttr( '%s.endFrame'%(AlembicNode) ) )
            if not startFrame:
                startFrame = sf
            elif sf < startFrame:
                startFrame = sf
            if not endFrame:
                endFrame = ef
            elif ef > endFrame:
                endFrame = ef
        mc.playbackOptions( animationStartTime=startFrame, minTime=startFrame, maxTime=endFrame, animationEndTime=endFrame )
        
#/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
def setRenderPatchs():
    '''
    设置 arnold batch render patchs，绑定为绝对路径；
    仅在maya环境有效；
    前提必须是reference带ns的形式，必须是流程工具整理的cache样式；
    '''
    # 结果: {u'chr_Wukong_default': u'Z:/Project/stmh/shot/cfx/000/0010/hair/v04/stmh_chr_Wukong/xgen/default/chr_Wukong_default.ma'} # 
    sceneReferenceDict = {}
    for RN in mc.ls( type='reference' ):
        if RN[-2:] == 'RN':
            if not mc.referenceQuery( RN, isNodeReferenced=1 ):
                if mc.referenceQuery( RN, isLoaded=1 ):
                    nameSpace = re.sub( '^:', '', mc.referenceQuery( RN, namespace=1 ), 0 )
                    sceneReferenceDict[nameSpace] = mc.referenceQuery( RN, filename=1 )
    # 结果: {'chr_Wukong_default': {'chr_Wukong_default:Wukong': u'Z:/Project/stmh/shot/cfx/000/0010/hair/v04/stmh_chr_Wukong/xgen/default/chr_Wukong_default.ma'}} # 
    scene_xgen = {}
    # 排除此类来历不明的nameSpace
    # Result: ('XG_RENDER_:chr_lxy_default:hair_lxy', 'xgen_chr_lxy_default:hair_lxy') # 
    palettes = []
    for p in xg.palettes():
        if not 'XG_RENDER_' in p and ':' in p:
            palettes.append( p )
    for xgen in palettes:
        xgen_split = re.split( ':', xgen )
        if xgen_split[0] in sceneReferenceDict:
            if not xgen_split[0] in scene_xgen:
                scene_xgen[ xgen_split[0] ] = {xgen:sceneReferenceDict[xgen_split[0]]}
            else:
                if not xgen in scene_xgen[xgen_split[0]]:
                    scene_xgen[ xgen_split[0] ][xgen] = sceneReferenceDict[xgen_split[0]]
    # {'chr_Wukong_default': {'chr_Wukong_default:Wukong': u'Z:/Project/stmh/shot/cfx/000/0010/hair/v04/stmh_chr_Wukong/xgen/default/chr_Wukong_default.ma'}}
    if scene_xgen:
        for ns in scene_xgen:
            for palette in scene_xgen[ns]:
                renderFileName = re.sub( '\.ma$', '', scene_xgen[ns][palette], 0 )
                collectionName = re.sub( '^.+:', '', palette, 0 )
                abcFile = '{}__{}.abc'.format(renderFileName,collectionName)
                if os.path.isfile(abcFile):
                    for description in xg.descriptions( palette ):
                        # 设置renderPatch abc路径，只能用.format()，不然一定报错，用%()可能会导致传参的数量不对称
                        shape = mc.listRelatives( description, s=1 )[0]
                        # 设置renderPatch: descriptionShape
                        mc.setAttr( '%s.aiUseAuxRenderPatch'%(shape), 1 )
                        mc.setAttr( '%s.aiAuxRenderPatch'%(shape), abcFile, type='string' )
                        # 设置renderPatch: patchs
                        xg.setAttr( 'renderer', 'Arnold Renderer', palette, description, 'RendermanRenderer' )
                        xg.setAttr( 'custom__arnold_useAuxRenderPatch', '1', palette, description, 'RendermanRenderer' )
                        xg.setAttr( 'custom__arnold_auxRenderPatch', abcFile, palette, description, 'RendermanRenderer' )
                    om.MGlobal.displayInfo( u'Set Batch Render Patchs:   %s 成功设置 render patchs。'%(palette) )
                else:
                    om.MGlobal.displayInfo( u'Set Batch Render Patchs:   %s 未找到 render patchs!!!!!!!!!!!!!!!!!'%(palette) )
    else:
        om.MGlobal.displayInfo( u'未找到可执行对象' )
#/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
def setPlayblastShader():
    '''
    设置所有 xgen 描述为 hairPhysicalShader 材质，用于拍屏预览；
    因为默认的 aiStandardHair 材质球在预览上非常糟糕；
    所以在导入 xgen 资产时，自动指定一个 hairPhysicalShader 材质；
    后续流程在打包环节调用的是服务器上的源资产，所以 sim 环节的制作文件修改是不影响后续的文件材质。
    '''
    # 获取 xgen 描述 shape
    xgmDes = mc.ls( type='xgmDescription' )
    if xgmDes:
        # 判断并创建材质SG
        m_SG = 'hairPhysicalShader_Playblast_SG'
        if not mc.ls( m_SG ):
            m_hair = mc.shadingNode( 'hairPhysicalShader', name='hairPhysicalShader_Playblast', asShader=1 )
            mc.setAttr('%s.intensityR'%(m_hair),0.2)
            mc.sets( name=m_SG, renderable=1, noSurfaceShader=1, empty=1 )
            mc.connectAttr( '%s.outColor'%( m_hair ), '%s.surfaceShader'%( m_SG ), f=1 )
        else:
            m_hair = 'hairPhysicalShader_Playblast'
        for des in xgmDes:
            # 判断着色组
            if mc.listConnections( '%s.instObjGroups'%( des ) ):
                # 判断 m_SG 是否在对象着色组里面
                if not m_SG in mc.listConnections( '%s.instObjGroups'%( des ) ):
                    mc.sets( des, e=1, forceElement=m_SG )
                    om.MGlobal.displayInfo( u'setPlayblastShader : %s 预览材质已设置为 %s。'%(des,m_hair) )
            else:
                mc.sets( des, e=1, forceElement=m_SG )
                om.MGlobal.displayInfo( u'setPlayblastShader : %s 预览材质已设置为 %s。'%(des,m_hair) )
#/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
def setXgenPreviewOff():
    '''
    '''
    if not mc.ls('xgmPreviewWarning'):
        if mc.ls('xgmRefreshPreview'):
            mc.delete('xgmRefreshPreview')
        mc.expression(n='xgmPreviewWarning',s='if( !`about -batch` ){\npython(\"xgui.createDescriptionEditor(False).setPreviewWarning(True)\");\n}')
    xg.setMessageLevel( 'warning', 0 )
    
    # xgg.DescriptionEditor.preview() # xgen 显示预览按钮
    # mc.XgCreateDescriptionEditor()
    # mc.xgmPreview(clean=1) #  xgen 关闭预览按钮 #  xgen 关闭预览按钮
    # xgg.DescriptionEditor.previewAutoAction.setChecked(True) # 设置 checkBox 为勾选
    # xgg.DescriptionEditor.onRefreshPreviewAuto() # xgen 自动更新预览，checkBox按钮
    # mc.xgmPreview(clean=1) #  xgen 关闭预览按钮 #  xgen 关闭预览按钮

#/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
def setGlobalWidth(value):
    '''
    maya内设置 custom_float_GlobalWidth；
    仅存在这个全局表达式时有效；
    用于导入资产制作时，提高宽度显示用于拍屏预览，及打包renderFile时还原为默认宽度；
    表达式样例：
    '$render=1.0000;#0.1,10.0\n$view=10.0000;#0.1,20.0\n$switch=2; # 1,2\n$fit=expand($switch,1,2);\nchoose($fit,$render,$view)'
    '''
    for p in xg.palettes():
        if 'custom_float_GlobalWidth' in xg.customAttrs(p):
            # print xg.getAttr('custom_float_GlobalWidth',p)
            exp = xg.getAttr('custom_float_GlobalWidth',p)
            # '$render=1.0000;#0.1,10.0\n$view=10.0000;#0.1,20.0\n$switch=2; # 1,2\n$fit=expand($switch,1,2);\nchoose($fit,$render,$view)'
            if re.search('\$switch\s*=\s*\d\s*;',exp):
                if not re.search('\$switch\s*=\s*%s\s*;'%(value),exp):
                    newExp = re.sub('\$switch\s*=\s*\d\s*;','$switch=%s;'%(value),exp)
                    xg.setAttr('custom_float_GlobalWidth',newExp,p)
                    om.MGlobal.displayInfo( u'setGlobalWidth : %s >> custom_float_GlobalWidth 已设置为 Switch = %s。'%(p,value) )
                    # print xg.getAttr('custom_float_GlobalWidth',p)
#/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
def editGlobalWidth(value,patch):
    '''
    读写的方式设置 custom_float_GlobalWidth；
    仅存在这个全局表达式时有效；
    用于导入资产制作时，提高宽度显示用于拍屏预览，及打包renderFile时还原为默认宽度；
    表达式样例：
    '$render=1.0000;#0.1,10.0\n$view=10.0000;#0.1,20.0\n$switch=2; # 1,2\n$fit=expand($switch,1,2);\nchoose($fit,$render,$view)'
    '''
    with open(patch,'r') as f:
        lines = f.readlines()
    with open(patch,'w') as f_w:
        for index, line in enumerate( lines ):
            try:
                if line[:25] == '	custom_float_GlobalWidth':
                    newLine = re.sub('\$switch\s*=\s*\d\s*;','$switch=%s;'%(value),line)
                    f_w.write(newLine)
                else:
                    f_w.write(line)
            except UnicodeDecodeError:
                # 通常try部分出错都是中文编码问题，如果出错则照搬这一行过去不做改动
                f_w.write(line)
                om.MGlobal.displayInfo( u'editFilePath : 读取文件第 %s 行时，出现 UnicodeDecodeError'%(index+1) )
#/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
def popMenu(self,point):
    '''
    列表右键菜单
    '''
    self.treeWidget_xgenCache.clearSelection()
    item = self.treeWidget_xgenCache.itemAt(point) # 获取 treeWidget 指定位置的 item
    # 如果鼠标位置获取到 item 才弹出右键菜单
    if item:
        from PySide2 import QtCore, QtGui, QtWidgets
        # menu
        popMenu = QtWidgets.QMenu(self)
        popMenu.setAttribute(QtCore.Qt.WA_DeleteOnClose)# pyqt pyside 设置窗口关闭时删除自身,清理内存非常有用！！！！
        # ------------------------------------------------------------
        # file
        menuFile = QtWidgets.QMenu(u'fileCache',popMenu)
        popMenu.addAction(menuFile.menuAction())
        fileData = item.data(0,4)
        if os.path.isfile(fileData):
            file = fileData
            fileName = item.text(0)
            # reference
            actFileReference = QtWidgets.QAction(u'Reference',menuFile)
            actFileReference.triggered.connect(lambda *args:[setFps(self),
                                                             mc.file(file,reference=1,ignoreVersion=1,groupLocator=1,mergeNamespacesOnClash=0,namespace=fileName),
                                                             setTimeSlider(self),
                                                             setRenderPatchs()])
            menuFile.addAction(actFileReference)
            filePath = re.sub( '/[^/]+$', '', file, 0 )
        else:
            filePath = fileData
        # open
        actFileOpen = QtWidgets.QAction(u'Open Folder',menuFile)
        actFileOpen.triggered.connect(lambda *args:os.startfile(filePath))
        menuFile.addAction(actFileOpen)
        # ------------------------------------------------------------
        # sim
        simData = item.data(2,4)
        if simData:
            popMenu.addSeparator()
            sim = simData
            simPath = re.sub( '/[^/]+$', '', simData, 0 )
            menuSim = QtWidgets.QMenu(u'simCache',popMenu)
            popMenu.addAction(menuSim.menuAction())
            # import
            menuSimImport = QtWidgets.QAction(u'Import',menuSim)
            menuSimImport.triggered.connect(lambda *args:[setFps(self),mc.file(sim,i=True,type="Alembic"),setTimeSlider(self)])
            menuSim.addAction(menuSimImport)
            # open
            menuSimOpen = QtWidgets.QAction(u'Open Folder',menuSim)
            menuSimOpen.triggered.connect(lambda *args:os.startfile(simPath))
            menuSim.addAction(menuSimOpen)
        # ------------------------------------------------------------
        popMenu.exec_(QtGui.QCursor.pos())
#/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
def setButton(self):
    '''
    设置 package，publish 状态
    '''
    packages,publishs = getSelected(self)
    if packages:
        self.pushButton_xgenCachePackage.setEnabled(True)
    else:
        self.pushButton_xgenCachePackage.setEnabled(False)
    if publishs:
        self.pushButton_xgenCachePublish.setEnabled(True)
    else:
        self.pushButton_xgenCachePublish.setEnabled(False)
        
#/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
def setCaches(self):
    '''
    设置 xgen cache 列表
    '''
    self.treeWidget_xgenCache.clear()
    localProjectShotPath,msg = self.getlocalProjectShotPath()
    if not localProjectShotPath:
        return
    #当前镜头的xgenCache路径
    xgenCachePath = '%s/PipelineCache/xgen'%( localProjectShotPath )
    xgenCacheFlies = getCaches(self)
    if xgenCacheFlies:
        from PySide2.QtCore import Qt
        from PySide2.QtGui import QColor
        from PySide2.QtWidgets import QTreeWidgetItem
        # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        def createItem(path,name,ver,sim,DriveMesh,xgCaches,xgPatches):
            newItem = QTreeWidgetItem()
            newItem.setText(0, name ) # 文件名
            red = QColor()
            red.setRgbF(1,0.4,0.4)
            yellow = QColor()
            yellow.setRgbF(0.8,0.8,0.3)
            blue = QColor()
            blue.setRgbF(0.4,0.4,1)
            # 判断顺序 41  21  31  41  51
            # 判断设置 ver，name Data
            if xgCaches:
                newItem.setData(0, 4, xgCaches[0] )
                newItem.setText(1, ver )
                newItem.setForeground(1,blue)
            else:
                if ver:
                    newItem.setData(0, 4, u'%s/%s/%s'%(path,name,ver) )
                    newItem.setText(1, ver )
                    newItem.setForeground(1,blue)
                else:
                    newItem.setData(0, 4, u'%s/%s'%(path,name) )
                    newItem.setText(1, 'null' )
                    newItem.setForeground(1,red)
            # 判断设置 sim
            if sim:
                newItem.setText(2, re.sub( '^.+/', '', re.sub( '/[^/]+$', '', sim, 0 ), 0 ) )
                newItem.setData(2, 4, sim )
                newItem.setForeground(2,blue)
            else:
                if ver:
                    newItem.setText(2, u'×' )
                    newItem.setForeground(2,yellow)
                else:
                    newItem.setText(2, u'×' )
                    newItem.setForeground(2,red)
            # 判断设置 DriveMesh
            if DriveMesh:
                newItem.setText(3, u'√' )
                newItem.setForeground(3,blue)
            else:
                if ver:
                    newItem.setText(3, u'×' )
                    newItem.setForeground(3,yellow)
                else:
                    newItem.setText(3, u'×' )
                    newItem.setForeground(3,red)
            # 判断设置 xgCaches
            if xgCaches:
                newItem.setText(4, u'√' )
                newItem.setForeground(4,blue)
            else:
                if ver:
                    newItem.setText(4, u'×' )
                    newItem.setForeground(4,yellow)
                else:
                    newItem.setText(4, u'×' )
                    newItem.setForeground(4,red)
            # 判断设置 xgPatches
            if xgPatches:
                newItem.setText(5, u'√' )
                newItem.setForeground(5,blue)
            else:
                if ver:
                    newItem.setText(5, u'×' )
                    newItem.setForeground(5,yellow)
                else:
                    newItem.setText(5, u'×' )
                    newItem.setForeground(5,red)
            newItem.setTextAlignment(1,Qt.AlignCenter)# 标题text 上下左右居中
            newItem.setTextAlignment(2,Qt.AlignCenter)# 标题text 上下左右居中
            newItem.setTextAlignment(3,Qt.AlignCenter)# 标题text 上下左右居中
            newItem.setTextAlignment(4,Qt.AlignCenter)# 标题text 上下左右居中
            newItem.setTextAlignment(5,Qt.AlignCenter)# 标题text 上下左右居中
            return newItem
        # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        #[ [ xgenCacheName, ver, simAbc, xgenDriveMesh, [ xgenMa, xgenPatchs, xgenCollectionsPath ], [xgenAbcs,...], ... ]
        for name,ver,sim,DriveMesh,xgCaches,xgPatches in xgenCacheFlies:
            self.treeWidget_xgenCache.addTopLevelItem(createItem(xgenCachePath,name,ver,sim,DriveMesh,xgCaches,xgPatches))
#/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
def getCaches(self):
    '''
    [ [ xgenCacheName, ver, simAbc, xgenDriveMesh, [ xgenMa, xgenPatchs, xgenCollectionsPath ], xgenAbcs ], ... ]
    
    以下是需要确定的缓存文件信息
    Z:/Cache/Cfx/Projects/moyaoan/jigong/shot/000/013/maya/PipelineCache/xgen/chr_lxy_new/v01/collections
    Z:/Cache/Cfx/Projects/moyaoan/jigong/shot/000/013/maya/PipelineCache/xgen/chr_lxy_new/v01/sim/v01/chr_lxy_default.abc
    Z:/Cache/Cfx/Projects/moyaoan/jigong/shot/000/013/maya/PipelineCache/xgen/chr_lxy_new/v01/collections/DriveMesh/DriveMesh.abc
    Z:/Cache/Cfx/Projects/moyaoan/jigong/shot/000/013/maya/PipelineCache/xgen/chr_lxy_new/v01/chr_lxy_new.ma
    Z:/Cache/Cfx/Projects/moyaoan/jigong/shot/000/013/maya/PipelineCache/xgen/chr_lxy_new/v01/chr_lxy_new__hair_lxy.abc
    Z:/Cache/Cfx/Projects/moyaoan/jigong/shot/000/013/maya/PipelineCache/xgen/chr_lxy_new/v01/chr_lxy_new__hair_lxy.xgen
    '''
    localProjectShotPath,msg = self.getlocalProjectShotPath()
    if not localProjectShotPath:
        return
    #当前镜头的xgenCache路径
    xgenCachePath = '%s/PipelineCache/xgen'%( localProjectShotPath )
    #找出当前镜头的xgenCaches
    #[ [ xgenCacheName, xgenCachePath ],... ]
    xgenCaches = []
    if os.path.exists(xgenCachePath):
        for xgenCacheName in os.listdir(xgenCachePath):
            #排除非文件夹
            if os.path.isdir( '%s/%s'%( xgenCachePath, xgenCacheName ) ):
                #正则排除命名字段前或后为‘_’的文件夹
                if not re.match( '^_.+$', xgenCacheName ) and not re.match( '^.+_$', xgenCacheName ) and os.path.isdir( '%s/%s'%(xgenCachePath,xgenCacheName) ):
                    xgenCaches.append([xgenCacheName,'%s/%s'%(xgenCachePath,xgenCacheName)])
    #找出当前镜头的xgenCacheFlies
    #[ [ xgenCacheName, ver, simAbc, xgenDriveMesh, [ xgenMa, xgenPatchs, xgenCollectionsPath ], xgenAbcs ], ... ]
    xgenCacheFlies = []
    if xgenCaches:
        for xgenCache in xgenCaches:
            verList = []
            for ver in os.listdir( xgenCache[1] ):
                if re.match( '^v\d{2}$', ver ):
                    verList.append( int( re.sub( '^v', '', ver, 0 ) ) )
            ver1 = False
            file_sim = False
            file_xgData = False
            file_renderFile = False
            file_renderPatch = False
            if verList:
                ver1 = 'v%02d'%( max(verList) )
                xgenCacheVerPath = '%s/%s'%( xgenCache[1], ver1 )
                simAbc = ''
                simPatchs = []
                xgenMa = ''
                xgenPatchs = []
                xgenAbcs = []
                xgenCollectionsPath = ''
                xgenDriveMesh = ''
                for i in os.listdir( xgenCacheVerPath ):
                    if os.path.isdir( '%s/%s'%( xgenCacheVerPath, i ) ):
                        if i == 'collections':
                            xgenCollectionsPath = '%s/collections'%( xgenCacheVerPath )
                            if os.path.isfile( '%s/DriveMesh/DriveMesh.abc'%( xgenCollectionsPath ) ):
                                xgenDriveMesh = '%s/DriveMesh/DriveMesh.abc'%( xgenCollectionsPath )
                        elif i == 'sim':
                            simVerList = []
                            for simVer in os.listdir( '%s/%s'%( xgenCacheVerPath, i ) ):
                                if re.match( '^v\d{2}$', simVer ):
                                    simVerList.append( int( re.sub( '^v', '', simVer, 0 ) ) )
                            if simVerList:
                                simVer1 = 'v%02d'%( max(simVerList) )
                                for simFile in os.listdir('%s/%s/%s'%( xgenCacheVerPath, i, simVer1 )):
                                    if re.match('%s\.abc'%(xgenCache[0]),simFile):
                                        simAbc = '%s/%s/%s/%s'%( xgenCacheVerPath, i, simVer1, simFile )
                                    elif re.match('^.+\.xgen$',simFile):
                                        simPatchs.append('%s/%s/%s/%s'%( xgenCacheVerPath, i, simVer1, simFile ))
                    elif re.match( '^%s\.ma$'%( xgenCache[0] ), i ):
                        xgenMa = '%s/%s'%( xgenCacheVerPath, i )
                    elif re.match( '^%s__.+\.xgen$'%( xgenCache[0] ), i ):
                        xgenPatchs.append( '%s/%s'%( xgenCacheVerPath, i ) )
                if xgenPatchs:
                    for i in xgenPatchs:
                        if os.path.isfile( re.sub( '\.xgen', '.abc', i, 0 ) ):
                            xgenAbcs.append( re.sub( '\.xgen', '.abc', i, 0 ) )
                
                if simAbc and simPatchs:
                    file_sim = simAbc
                if xgenDriveMesh:
                    file_xgData = xgenDriveMesh
                if xgenMa and xgenPatchs:
                    file_renderFile = [ xgenMa, xgenPatchs, xgenCollectionsPath ]
                if xgenPatchs and len(xgenPatchs)==len(xgenAbcs):
                    file_renderPatch = xgenAbcs
                # if xgenMa and xgenPatchs and len(xgenPatchs)==len(xgenAbcs) and xgenDriveMesh:
                #     xgenCacheFlies.append( [ xgenCache[0], ver1, xgenMa, xgenPatchs, xgenAbcs, xgenCollectionsPath, xgenDriveMesh ] )
            xgenCacheFlies.append( [ xgenCache[0], ver1, file_sim, file_xgData, file_renderFile, file_renderPatch ] )
    
    return xgenCacheFlies
    #[ [ xgenCacheName, ver, simAbc, xgenDriveMesh, [ xgenMa, xgenPatchs, xgenCollectionsPath ], xgenAbcs ], ... ]
#/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
def getSelected(self):
    '''
    return [ packageCacheName, ... ],[ publishCacheName, ... ]
    '''
    packages = []
    publishs = []
    for obj in self.treeWidget_xgenCache.selectedItems():
        if obj.text(1)[0]=='v' and not obj.text(2)==u'×':
            packages.append( obj.text(0) )
            if obj.text(3)==u'√' and obj.text(4)==u'√' and obj.text(5)==u'√':
                publishs.append( obj.text(0) )
    return packages,publishs
#/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
def packageCache(self):
    '''
    打包本地解算缓存，生成可用的渲染文件，用于上传
    '''
    if mc.file( q=1,sceneName=1 ):
        mc.warning( u'package cache: 请先保存当前场景,新开空场景执行' )
        return
    
    localProjectShotPath,msg = self.getlocalProjectShotPath()
    if not localProjectShotPath:
        mc.warning( msg )
        return
    
    #G:/py/cfx_pipeline_tool/temp/Project_path/moyaoan/jigong/shot/000/001/maya/PipelineCache/xgen/chr_lxy_new
    #当前镜头的xgenCache路径
    xgenCachePath = '%s/PipelineCache/xgen'%( localProjectShotPath )
    
    #[ cacheName, ... ]
    packages,publishs = getSelected(self)
    if not packages:
        mc.warning( u'package cache: 未选择可以打包的缓存' )
        return
    
    # 找出当前镜头的xgenCaches
    # [[cacheName,cachePath],...]
    xgenCaches = []
    if os.path.exists(xgenCachePath):
        for xgenCacheName in os.listdir(xgenCachePath):
            #排除非文件夹
            if os.path.isdir( '%s/%s'%( xgenCachePath, xgenCacheName ) ):
                #正则排除命名字段前或后为‘_’的文件夹
                if not re.match( '^_.+$', xgenCacheName ) and not re.match( '^.+_$', xgenCacheName ):
                    if xgenCacheName in packages:
                        xgenCaches.append([xgenCacheName,'%s/%s'%(xgenCachePath,xgenCacheName)])
    
    fixRoot = self.checkBox_xgenCacheFixRootOffset.isChecked()
    if self.radioButton_xgenCacheFixByStartFrame.isChecked():
        fixRoot_frame = 'start'
    else:
        fixRoot_frame = self.spinBox_xgenCacheFixByFrame.value()
    op_1 = self.checkBox_xgenCachePackegeProcess1.isChecked()
    op_2 = self.checkBox_xgenCachePackegeProcess2.isChecked()
    op_3 = self.checkBox_xgenCachePackegeProcess3.isChecked()
    if mc.file( q=1,sceneName=1 ):
        mc.warning( u'Create render file: 请先保存当前场景,新开空场景运行' )
        return
    if op_1:
        act_1 = export_simCurve_to_xgData( self, xgenCaches, fixRoot, fixRoot_frame )
        if not act_1:
            return
        else:
            if act_1==True:
                om.MGlobal.displayInfo( u'Export simCurve to xgData: 缓存分拣输出完成！！' )
            else:
                om.MGlobal.displayInfo( u'Export simCurve to xgData: %s缓存分拣输出完成'%(act_1) )
    if op_2:
        act_2 = create_render_file( self, xgenCaches )
        if not act_2:
            return
        else:
            if act_2==True:
                om.MGlobal.displayInfo( u'Create file: 创建renderFile完成！！' )
            else:
                om.MGlobal.displayInfo( u'Create file: %s已成功创建renderFile'%(act_2) )
    if op_3:
        act_3 = export_patches_for_batch_render( self, xgenCaches )
        if not act_3:
            return
        else:
            if act_3==True:
                om.MGlobal.displayInfo( u'Export patches for batch render: 导出成功！！' )
            else:
                om.MGlobal.displayInfo( u'Export patches for batch render: %s导出成功'%(act_3) )
#/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
def setFps(self):
    '''
    设置帧速率
    '''
    fps = self.pro.fps()
    if not mc.currentUnit( q=1, time=1 ) == fps:
        mc.currentUnit( time=fps )
#/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
def export_simCurve_to_xgData( self, xgenCaches, fixRoot, fixRoot_frame ):
    '''
    新开空场景
    导入growMesh+simCurve
    分别导出每个部位的guide或animWire

    曲线命名规则：collection__description__driveMode__curveName
    如下
       guide : hair_lxy__short_hair_binjiao__guide__curve12
    animWire : hair_lxy__short_hair_binjiao__animWire__curve12
    '''
    # G:/py/cfx_pipeline_tool/temp/Project_path/moyaoan/jigong/shot/000/001/maya/PipelineCache/xgen/chr_lxy_new/v01/sim/v03
    # 找出当前镜头的simCaches
    # [[xgenCacheName,simCacheFile],...]
    simCaches = []
    if xgenCaches:
        for xgenCache in xgenCaches:
            verList = []
            for ver in os.listdir( xgenCache[1] ):
                if re.match( '^v\d{2}$', ver ):
                    verList.append( int( re.sub( '^v', '', ver, 0 ) ) )
            if verList:
                ver1 = 'v%02d'%( max(verList) )
                simCachePath = '%s/%s/sim'%( xgenCache[1], ver1 )
                if os.path.exists( simCachePath ):
                    verList = []
                    for ver in os.listdir( simCachePath ):
                        if re.match( '^v\d{2}$', ver ):
                            verList.append( int( re.sub( '^v', '', ver, 0 ) ) )
                    if verList:
                        ver2 = 'v%02d'%( max(verList) )
                        simCacheVerPath = '%s/%s'%( simCachePath, ver2 )
                        for simCache in os.listdir( simCacheVerPath ):
                            if re.match( '^%s\.abc$'%(xgenCache[0]), simCache ):
                                simCaches.append( [ xgenCache[0], '%s/%s'%(simCacheVerPath, simCache) ] )
                                break
    
    if not simCaches:
            mc.warning( u'Export simCurve to xgData: 未找到 simCaches' )
            return False
    
    message = ''
    # [[xgenCacheName,simCacheFile],...]
    for xgenCacheName,simCacheFile in simCaches:
        # 打开新场景
        mc.file( force=1, newFile=1 )

        # 禁用显示
        mc.select(cl=1)
        for mp in mc.getPanel( type='modelPanel' ):
            mc.isolateSelect(mp,state=1) # 启用隔离显示，减轻gpu负担，提高cache速度
            # mc.modelEditor(mp,e=1,allObjects=0) # 关闭所有 modelPanel 的物体显示，减轻显示负担，提高cache速度
        
        # 设置帧速率
        setFps(self)
        # 导入解算缓存
        mc.file( simCacheFile, i=True, type="Alembic" )
        
        # 根据命名规则识别场景中的缓存：simGuide，simAnimWire，driveMesh
        # nurbsCurve命名规则: hair_lxy__short_hair_binjiao__guide__curve12
        simGuide = []
        for i in mc.ls( '*__guide__*', fl=1, type='nurbsCurve' ):
            if mc.listRelatives( i, parent=1 ):
                guide = mc.listRelatives( i, parent=1 )[0]
                if guide not in simGuide:
                    simGuide.append( guide )
        # nurbsCurve命名规则: hair_lxy__short_hair_binjiao__animWire__curve12
        simAnimWire = []
        for i in mc.ls( '*__animWire__*', fl=1, type='nurbsCurve' ):
            if mc.listRelatives( i, parent=1 ):
                animWire = mc.listRelatives( i, parent=1 )[0]
                if animWire not in simAnimWire:
                    simAnimWire.append( animWire )
        driveMesh = []
        for i in mc.ls( fl=1, type='mesh' ):
            if mc.listRelatives( i, parent=1 ):
                mesh = mc.listRelatives( i, parent=1 )[0]
                if mesh not in driveMesh:
                    driveMesh.append( mesh )
        # print simGuide
        # print simAnimWire
        # print driveMesh
        
        warningList = ''
        
        # 创建导出列表字典，嵌套层级： cacheDict = { driveMode:{ collections:{ descriptions:[ [curve,...], cacheFile ] } } }
        cacheDict = { 'guide':{},'animWire':{} }
        for driveMode in [ simGuide, simAnimWire ]:
            for i in driveMode:
                split_i = re.split( '__', i )
                # 结果: ['hair_lxy', 'long_hair_back', 'guide', 'curve1'] # 
                if not len(split_i)==4:
                    warningList += i+', '
                    continue
                path = re.sub( 'sim/.+$', 'collections/%s/%s'%( split_i[0], split_i[1] ), simCacheFile, 0 )
                if split_i[2] == 'animWire':
                    # if not os.path.exists( '%s/AnimWires1'%( path ) ):
                    #     mc.warning( u'Export simCurve to xgData: 尝试输出缓存失败，路径： %s/AnimWires1 不存在！ 检查xgData文件是否正确'%(path) )
                    #     return
                    cacheFile = '%s/AnimWires1/wires.abc'%( path )
                else:
                    # if not os.path.exists( path ):
                    #     mc.warning( u'Export simCurve to xgData: 尝试输出缓存失败，路径： %s 不存在！ 检查xgData文件是否正确'%(path) )
                    #     return
                    cacheFile = '%s/guides.abc'%( path )
                if split_i[0] not in cacheDict[ split_i[2] ]:
                    cacheDict[ split_i[2] ][ split_i[0] ] = { split_i[1]:[ [ i ], cacheFile ] }
                else:
                    if split_i[1] not in cacheDict[ split_i[2] ][ split_i[0] ]:
                        cacheDict[ split_i[2] ][ split_i[0] ][ split_i[1] ] = [ [ i ], cacheFile ]
                    else:
                        cacheDict[ split_i[2] ][ split_i[0] ][ split_i[1] ][0] += [ i ]
        
        if warningList:
            mc.warning( u'Export simCurve to xgData: 缓存中的曲线 %s 命名规则有误，请检查资产再重新输出！'%(warningList) )
            return
        
        # for key1 in cacheDict:
        #     for key2 in cacheDict[key1]:
        #         for key3 in cacheDict[key1][key2]:
        #             print key1, key2, key3,':',cacheDict[key1][key2][key3]
        
        #################################################################################################################################
        #################################################################################################################################
        #################################################################################################################################
        '''
        多个 description 同时调用相同的驱动曲线，临时补丁方案，
        如果需要改动，则需要重新定义新的解算曲线导出方案，
        生成补丁内容的方式请使用 pipeline 》 asset 》 xgen 》 Xgen Patch Solution  按钮生成，
        补丁文本内容需要打在 driveMesh 的 notes 属性中，
        '''
        
        patchMesh=''
        for i in mc.ls( fl=1, type='mesh' ):
            if 'notes' in mc.listAttr( i ):
                if mc.getAttr( '%s.notes'%( i ) ):
                    patchMesh=i
                    break
        # cacheDict = { driveMode:{ collections:{ descriptions:[ [curve,...], cacheFile ] } } }
        if patchMesh:
            patchNote = mc.getAttr( '%s.notes'%( patchMesh ) )
            splitNote = re.split('|', patchNote )
            for i in splitNote:
                if i:
                    d = re.split( ':', i )
                    patchCollection, patchDescription = re.split( '__', d[0] )
                    curves = re.split(',', d[1] )
                    patchCurve = []
                    # 检测曲线是否在场景中存在
                    for curve in curves:
                        if curve in simGuide or curve in simAnimWire:
                            patchCurve.append(curve)
                    if patchCurve:
                        patchDriveMode = re.split( '__', patchCurve[0] )[2]
                        path = re.sub( 'sim/.+$', 'collections/%s/%s'%( patchCollection, patchDescription ), simCacheFile, 0 )
                        if patchDriveMode == 'animWire':
                            # if not os.path.exists( '%s/AnimWires1'%( path ) ):
                            #     mc.warning( u'Export simCurve to xgData: 尝试输出缓存失败，路径： %s/AnimWires1 不存在！ 检查xgData文件是否正确'%(path) )
                            #     return
                            cacheFile = '%s/AnimWires1/wires.abc'%( path )
                        else:
                            # if not os.path.exists( path ):
                            #     mc.warning( u'Export simCurve to xgData: 尝试输出缓存失败，路径： %s 不存在！ 检查xgData文件是否正确'%(path) )
                            #     return
                            cacheFile = '%s/guides.abc'%( path )
                        cacheDict[patchDriveMode][patchCollection][patchDescription] = [ patchCurve, cacheFile ]
        #################################################################################################################################
        #################################################################################################################################
        #################################################################################################################################
        # 获取并设置cache输出帧范围
        if not mc.ls( fl=1, type='AlembicNode' ):
            startTime = 950
            endTime = 951
        else:
            abcNode = mc.ls( fl=1, type='AlembicNode' )[0]
            startTime = round( mc.getAttr( '{0}.startFrame'.format(abcNode) ) )
            endTime = round( mc.getAttr( '{0}.endFrame'.format(abcNode) ) )
        mc.playbackOptions( animationStartTime=startTime, minTime=startTime, maxTime=endTime, animationEndTime=endTime )
        #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        # animWire 方式曲线导出，临时应急解决方案，后期需要整合优化
        def animWireAlembicExport( obj, path, uvWrite, startTime, endTime, sample ):
            #obj = mc.ls( sl=True, fl=True )
            #path = r'Z:\Resource\Groups\KCS\cfx\tools\py\cfx_pipeline_tool\temp\aa.abc'
            #sample = 1
            if uvWrite:
                UV='-uvWrite '
            else:
                UV=''
            NumList = []
            for i in obj:
                cvName = re.split( '__animWire__', i )[1]
                cvNum = re.search( '\d+$', cvName )
                if cvNum:
                    NumList.append( [ int( cvNum.group() ), i ] )
                else:
                    NumList.append( [ 0, i ] )
            NumList.sort()
            grpList = []
            for i in NumList:
                grpList.append( i[1] )
            group = mc.group( grpList )

            root = ''
            for i in [ group ]:
                root +='-root {0} '.format( i )
                #print root
            
            #startTime = mc.playbackOptions( q=True, minTime=True )
            #endTime = mc.playbackOptions( q=True, maxTime=True )
            # AbcExport -j "-frameRange 1 1 -worldSpace -writeVisibility -dataFormat ogawa -root |pSphere1 -file Z:/Cache/Cfx/Projects/moyaoan/jigong/shot/013/208/maya/TempCache/t1.abc";
            
            Command = '-frameRange {0} {1} -step {2} {3}-worldSpace -writeVisibility -dataFormat ogawa {4} -file {5}'.format( startTime, endTime, sample, UV, root, path )
            mc.AbcExport( jobArg = Command )
        #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        # guide 方式曲线导出，临时应急解决方案，后期需要整合优化
        def guideAlembicExport( obj, path, uvWrite, startTime, endTime, sample ):
            #obj = mc.ls( sl=True, fl=True )
            #path = r'Z:\Resource\Groups\KCS\cfx\tools\py\cfx_pipeline_tool\temp\aa.abc'
            #sample = 1
            if uvWrite:
                UV='-uvWrite '
            else:
                UV=''
            NumList = []
            for i in obj:
                cvName = re.split( '__guide__', i )[1]
                cvNum = re.search( '\d+$', cvName )
                if cvNum:
                    NumList.append( [ int( cvNum.group() ), i ] )
                else:
                    NumList.append( [ 0, i ] )
            NumList.sort()
            grpList = []
            for i in NumList:
                grpList.append( i[1] )
            group = mc.group( grpList )

            root = ''
            for i in [ group ]:
                root +='-root {0} '.format( i )
                #print root
            
            #startTime = mc.playbackOptions( q=True, minTime=True )
            #endTime = mc.playbackOptions( q=True, maxTime=True )
            # AbcExport -j "-frameRange 1 1 -worldSpace -writeVisibility -dataFormat ogawa -root |pSphere1 -file Z:/Cache/Cfx/Projects/moyaoan/jigong/shot/013/208/maya/TempCache/t1.abc";
            
            Command = '-frameRange {0} {1} -step {2} {3}-worldSpace -writeVisibility -dataFormat ogawa {4} -file {5}'.format( startTime, endTime, sample, UV, root, path )
            mc.AbcExport( jobArg = Command )
        #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        
        # 导出 driveMesh
        driveMeshPath = re.sub( 'sim/.+$', 'collections/DriveMesh', simCacheFile, 0 )
        driveMeshFile = driveMeshPath+'/DriveMesh.abc'
        if not os.path.exists(driveMeshPath):
            os.makedirs(driveMeshPath)
        alembicExport( driveMesh, driveMeshFile, 1, startTime, endTime, 1 )
        om.MGlobal.displayInfo( u'driveMesh : %s 成功输出至 %s'%( xgenCacheName, driveMeshFile ) )

        # 修正根部偏移
        # 此处不能放在导出 driveMesh 之前，首先是卡，第二是出的 driveMesh 可能会出问题，导致输出 render patch 时各种崩溃
        if fixRoot:
            if fixRoot_frame == 'start':
                fixRoot_frame = startTime
            fix_root_offset( simGuide+simAnimWire, driveMesh, re.sub( '/[^/]+$', '', simCacheFile, 0 ), fixRoot_frame )
            om.MGlobal.displayInfo( u'fixRoot : 根部已经锁定' )
        
        #cacheDict = { driveMode:{ collections:{ descriptions:[ [curve,...], cacheFile ] } } }
        for key1 in cacheDict:
            for key2 in cacheDict[key1]:
                for key3 in cacheDict[key1][key2]:
                    exportPath = re.sub('/[^/]+$','',cacheDict[key1][key2][key3][1],0)
                    if not os.path.exists(exportPath):
                        os.makedirs(exportPath)
                    if key1=='animWire':
                        # AbcExport -j "-frameRange 1 1 -worldSpace -writeVisibility -dataFormat ogawa -root |pSphere1 -file Z:/Cache/Cfx/Projects/moyaoan/jigong/shot/013/208/maya/TempCache/t1.abc";
                        animWireAlembicExport( cacheDict[key1][key2][key3][0], cacheDict[key1][key2][key3][1], 0, startTime, endTime, 1 )
                    else:
                        guideAlembicExport( cacheDict[key1][key2][key3][0], cacheDict[key1][key2][key3][1], 0, startTime, endTime, 1 )
                        # alembicExport( cacheDict[key1][key2][key3][0], cacheDict[key1][key2][key3][1], 0, startTime, endTime, 1 )
                    om.MGlobal.displayInfo( u'%s : %s >> %s, 成功输出至 %s'%( key1, key2, key3, cacheDict[key1][key2][key3][1] ) )
        om.MGlobal.displayInfo( u'export simCurve to xgData: %s 缓存分拣输出完成'%( xgenCacheName ) )
        message += '%s, '%( xgenCacheName )
    mc.file( force=1, newFile=1 )
    if message:
        return message
    return True
#/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
def create_render_file( self, xgenCaches ):
    '''
    创建渲染文件
    '''
    # G:/py/cfx_pipeline_tool/temp/Project_path/moyaoan/jigong/shot/000/001/maya/PipelineCache/xgen/chr_lxy_new/v01/temp/temp_asset.ma
    # [[cacheName,driveMesh,[patch,...]],...]
    simCaches = []
    if xgenCaches:
        for xgenCache in xgenCaches:
            verList = []
            for ver in os.listdir( xgenCache[1] ):
                if re.match( '^v\d{2}$', ver ):
                    verList.append( int( re.sub( '^v', '', ver, 0 ) ) )
            if verList:
                verPath = '%s/%s'%(xgenCache[1],'v%02d'%( max(verList) ))
                simPath = '%s/sim'%(verPath)
                # 找出当前镜头的patchs
                patchs = []
                simVerList = []
                if os.path.exists(simPath):
                    for simVer in os.listdir( simPath ):
                        if re.match( '^v\d{2}$', simVer ):
                            simVerList.append( int( re.sub( '^v', '', simVer, 0 ) ) )
                if simVerList:
                    simVerPath = '%s/%s'%(simPath,'v%02d'%( max(simVerList) ))
                    for patch in os.listdir(simVerPath):
                        if re.match('.+\.xgen$',patch):
                            patchs.append('%s/%s'%(simVerPath,patch))
                # 找出当前镜头的driveMeshs
                driveMesh = '%s/collections/DriveMesh/DriveMesh.abc'%( verPath )
                if patchs and os.path.isfile(driveMesh):
                    simCaches.append( [ xgenCache[0], driveMesh, patchs ] )
    # print simCaches
    if not simCaches:
            mc.warning( u'Create render file: 未找到 simCaches，或未分拣 simCaches' )
            return False
    message = ''
    # [[cacheName,driveMesh,[patch,...]],...]
    for cacheName,driveMesh,patchs in simCaches:
        # 生成renderFile路径
        renderFilePath = re.sub( '/collections/DriveMesh/DriveMesh.abc$', '', driveMesh )
        renderFile = '%s/%s.ma'%( renderFilePath, cacheName )
        # [[simPatchName,simPatch,srcPatchName,srcPatch,renderPatchName,renderPatch],...]
        allPatchs = []
        # 通过patchs中xgDataPath的第二个路径找到源资产内容
        src_asset = ''
        patchXgDatas = []
        for patch in patchs:
            simPatchName = re.sub('^.+/','',patch)
            matchCollectionName = re.split('__',simPatchName)[-1]
            srcPatchName = ''
            srcPatch = ''
            renderPatchName = '%s__%s'%(cacheName,matchCollectionName)
            renderPatch = '%s/%s'%(renderFilePath,renderPatchName)
            # 查询xgData
            src_path = ''
            with open( patch,"r") as f:
                lines = f.readlines()
                for line in lines:
                    if line[:13] == r'	xgDataPath		':
                        if ';' in line[13:]:
                            temp_path = re.sub( '\n$', '', line[13:], 0 )
                            temp_path = re.sub( r'\\', '/', temp_path, 0 )
                            split_path = re.split(';',temp_path)
                            patchXgDatas.append([ re.sub('/$','',split_path[0]), re.sub('/$','',split_path[1]) ])
                            src_path = re.sub( '/collections/[^/]+$', '', split_path[1], 0 )
                        else:
                            mc.warning(u'%s : xgData 非双重路径，获取源资产失败！'%(patch))
                        break
            # 查询xgenAsset
            if src_path:
                for assetFile in os.listdir(src_path):
                    if re.match('.+\.ma',assetFile):
                        src_asset = '%s/%s'%(src_path,assetFile)
                    if re.match('.+__%s'%(matchCollectionName),assetFile):
                        srcPatchName = assetFile
                        srcPatch = '%s/%s'%(src_path,srcPatchName)
            if not srcPatchName:
                mc.warning(u'%s : 未找到源资产关联的 patch'%(patch))
                return False
            allPatchs.append([simPatchName,patch,srcPatchName,srcPatch,renderPatchName,renderPatch])
        # print patchXgDatas
        if not src_asset or not patchXgDatas:
            mc.warning(u'%s : 未找到源资产信息'%(cacheName))
            return False
        # 打开源资产
        mc.file( src_asset, open=1, force=1, ignoreVersion=1, typ="mayaAscii" )
        om.MGlobal.displayInfo( u'成功打开文件： %s'%(src_asset) )
        
        # xgen pv off
        setXgenPreviewOff()
        
        # 查询collection绑定面片
        # Result: ('XG_RENDER_:chr_lxy_default:hair_lxy', 'xgen_chr_lxy_default:hair_lxy') # 
        # 排除此类来历不明的nameSpace
        palettes = []
        for p in xg.palettes():
            if not 'XG_RENDER_' in p:
                palettes.append( p )
        # 获取场景中所有的生长面
        growMeshs = []
        for p in palettes:
            for d in xg.descriptions( p ):
                for g in xg.boundGeometry( p, d ):
                    if g not in growMeshs:
                        growMeshs.append( g )
        # 删除生长面构建历史，隐藏显示
        for growMesh in growMeshs:
            mc.setAttr( '%s.visibility'%(growMesh), 0 )
            mc.delete( growMesh, constructionHistory=1 )
        # 断开nhair动力学输出曲线跟xgenGuide的关联
        xgmMakeGuides = mc.ls( fl=1, type='xgmMakeGuide' )
        if xgmMakeGuides:
            for xgmMakeGuide in xgmMakeGuides:
                connected = mc.connectionInfo( '%s.override'%( xgmMakeGuide ), sourceFromDestination=True )
                if connected:
                    mc.disconnectAttr( connected, '%s.override'%( xgmMakeGuide ) )
        # 选择xgen collection，导出所选
        mc.select( palettes )
        mc.file( renderFile, exportSelected=1, force=1, options="v=0", typ="mayaAscii" )
        om.MGlobal.displayInfo( u'成功导出render文件： %s'%(renderFile) )
        
        # 修改导出ma的patch名称
        # [[simPatchName,simPatch,srcPatchName,srcPatch,renderPatchName,renderPatch],...]
        srcPatchNames = []
        renderPatchNames = []
        for allPatch in allPatchs:
            srcPatchNames.append(allPatch[2])
            renderPatchNames.append(allPatch[4])
        editXgenAsset( renderFile, renderFile, srcPatchNames, renderPatchNames )
        om.MGlobal.displayInfo( u'成功修改render文件patch名称： %s'%(renderFile) )
        
        # 整合xgData为独立缓存
        if self.buttonGroup_xgData.checkedId()==1:
            for dstPath,srcPath in patchXgDatas:
                srcFiles = dirlist(srcPath)
                for srcFile in srcFiles:
                    dstFile = re.sub(srcPath,dstPath,srcFile)
                    if not os.path.isfile(dstFile):
                        dstFile = re.sub(r'\\','/',dstFile)
                        filePath = re.sub('/[^/]+$','',dstFile)
                        if not os.path.exists(filePath):
                            os.makedirs(filePath)
                        shutil.copyfile(srcFile,dstFile)
                om.MGlobal.displayInfo( u'xgData : %s 整合完成。'%(dstPath) )
        
        # 复制xgen patch,修改xgen patch中的FXModule为启用
        # [[simPatchName,simPatch,srcPatchName,srcPatch,renderPatchName,renderPatch],...]
        for allPatch in allPatchs:
            # 查询xgData的guide及animwires信息
            XgDataPath = ''
            with open( allPatch[1],"r") as f:
                lines = f.readlines()
                for line in lines:
                    if line[:13] == r'	xgDataPath		':
                        line = re.sub( '\n$', '', line[13:] )
                        line = re.sub( ';.+$', '', line )
                        line = re.sub( r'\\', '/', line )
                        line = re.sub( '/$', '', line )
                        XgDataPath = line
                        break
                    else:
                        pass
            dirveInfo = {}
            if XgDataPath:
                for description in os.listdir( XgDataPath ):
                    if os.path.isfile( '%s/%s/guides.abc'%( XgDataPath, description ) ):
                        dirveInfo[description] = 'guide'
                    elif os.path.isfile( '%s/%s/AnimWires1/wires.abc'%( XgDataPath, description ) ):
                        dirveInfo[description] = 'animWire'
            
            shutil.copyfile( allPatch[1], allPatch[5] )
            activeDirveCurve( allPatch[5], dirveInfo )
            # activeFXModule( allPatch[5] )
            om.MGlobal.displayInfo( u'成功复制xgen patch： %s'%(allPatch[5]) )
        
        # open render file
        mc.file( renderFile, open=1, force=1, ignoreVersion=1, typ="mayaAscii" )
        om.MGlobal.displayInfo( u'成功打开render文件： %s'%(renderFile) )
        # 设置帧速率
        setFps(self)

        # xgen pv off
        setXgenPreviewOff()
        
        # 导入growMesh+simCurve.abc并且关联mesh
        mc.AbcImport(driveMesh,fitTimeRange=1,setToStartFrame=1,connect='/')
        om.MGlobal.displayInfo( u'成功关联缓存： %s'%(driveMesh) )
        
        # 还原xgen全局宽度
        setGlobalWidth(1)

        # 设置 arnold batch render patch，绑定为绝对路径；紧在maya环境有效
        if self.buttonGroup_xgenCache.checkedId()==1:
            renderFileName = re.sub( r'\.ma$', '', renderFile, 0 )
            for palette in palettes:
                for description in xg.descriptions( palette ):
                    # 设置renderPatch abc路径，只能用.format()，不然一定报错，用%()可能会导致传参的数量不对称
                    abcFile = '{}__{}.abc'.format(renderFileName,palette)
                    shape = mc.listRelatives( description, s=1 )[0]
                    # 设置renderPatch: descriptionShape
                    mc.setAttr( '%s.aiUseAuxRenderPatch'%(shape), 1 )
                    mc.setAttr( '%s.aiAuxRenderPatch'%(shape), abcFile, type='string' )
                    # 设置renderPatch: patchs
                    xg.setAttr( 'renderer', 'Arnold Renderer', palette, description, 'RendermanRenderer' )
                    xg.setAttr( 'custom__arnold_useAuxRenderPatch', '1', palette, description, 'RendermanRenderer' )
                    xg.setAttr( 'custom__arnold_auxRenderPatch', abcFile, palette, description, 'RendermanRenderer' )
        mc.file(save=1)
        # mc.file( renderFile, open=1, force=1, ignoreVersion=1, typ="mayaAscii" )
        # # 修改xgen为增量模式
        # # 测试结果：并没有找到增量模式在pipline中有什么理想的应用，base和delta可以指向绝对路径，但是render时，渲染器认不到此绝对路径，只能认到跟ma文件同级目录
        # for palette in palettes:
        #     mc.setAttr( '%s.xgBaseFile'%( palette ), '%s/%s'%( renderFilePath, mc.getAttr( '%s.xgFileName'%( palette ) ) ), type='string' )
        #     mc.setAttr( '%s.xgExportAsDelta'%( palette ), 1 )
        #     mc.setAttr( '%s.xgFileName'%( palette ), '', type='string' )
        # mc.file(save=1)
        om.MGlobal.displayInfo( u'Create render file： %s 已成功创建renderFile至 %s'%( cacheName, renderFile ) )
        message += '%s, '%( cacheName )
    mc.file( force=1, newFile=1 )
    if message:
        return message
    return True
#/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
def export_patches_for_batch_render( self, xgenCaches ):
    '''
    创建 xgen patches
    '''
    # G:/py/cfx_pipeline_tool/temp/Project_path/moyaoan/jigong/shot/000/001/maya/PipelineCache/xgen/chr_lxy_new/v01/temp/temp_asset.ma
    # 找出当前镜头的xgenMas
    xgenMas = []
    if xgenCaches:
        for xgenCache in xgenCaches:
            verList = []
            for ver in os.listdir( xgenCache[1] ):
                if re.match( '^v\d{2}$', ver ):
                    verList.append( int( re.sub( '^v', '', ver, 0 ) ) )
            if verList:
                ver1 = 'v%02d'%( max(verList) )
                xgenMa = '%s/%s/%s.ma'%( xgenCache[1], ver1, xgenCache[0] )
                if os.path.isfile(xgenMa):
                    xgenMas.append( [ xgenCache[0], xgenMa ] )
    if not xgenMas:
        mc.warning( u'Export patches for batch render: 当前镜头未找到可执行的ma文件，请先创建renderFile' )
        return False
    
    message = ''

    for xgenMa in xgenMas:
        mc.file( xgenMa[1], open=1, force=1, ignoreVersion=1, typ="mayaAscii" )
        # 设置帧速率
        # setFps(self)
        
        # 禁用显示
        mc.select(cl=1)
        for mp in mc.getPanel( type='modelPanel' ):
            mc.isolateSelect(mp,state=1) # 启用隔离显示，减轻gpu负担，提高cache速度
            # mc.modelEditor(mp,e=1,allObjects=0) # 关闭所有 modelPanel 的物体显示，减轻显示负担，提高cache速度
        
        maya_f = mc.file( q=1,sceneName=1 )
        
        growMeshs = []

        # 排除此类来历不明的nameSpace
        # Result: ('XG_RENDER_:chr_lxy_default:hair_lxy', 'xgen_chr_lxy_default:hair_lxy') # 
        palettes = []
        for p in xg.palettes():
            if not 'XG_RENDER_' in p:
                palettes.append( p )
        
        for p in palettes:
            growMesh = []
            for d in xg.descriptions( p ):
                for g in xg.boundGeometry( p, d ):
                    if not g in growMesh:
                        growMesh.append( g )
            if growMesh:
                growMeshs.append( [ p, growMesh ] )
        
        if not growMesh:
            mc.warning( u'Export patches for batch render: 找不到xgen collection' )
            return False
        
        if not mc.ls( fl=1, type='AlembicNode' ):
            startTime = 950
            endTime = 951
        else:
            abcNode = mc.ls( fl=1, type='AlembicNode' )[0]
            startTime = mc.getAttr( '%s.startFrame'%(abcNode) )
            endTime = mc.getAttr( '%s.endFrame'%(abcNode) )
        mc.playbackOptions( animationStartTime=startTime, minTime=startTime, maxTime=endTime, animationEndTime=endTime )
        
        for p, growMesh in growMeshs:
            mc.select(growMesh)
            obj = mc.ls( sl=True, fl=True, long=1 )
            
            path = re.sub( r'/[^/]+\.ma$', '/', maya_f, 0 )
            fileName = re.sub( r'^.+/', '', maya_f, 0 )
            fileName = re.sub( r'\.ma$', '', fileName, 0 )
            abcFile = '%s%s__%s.abc'%(path,fileName,p)
            # path = r'Z:\Resource\Groups\KCS\cfx\tools\py\cfx_pipeline_tool\temp\aa.abc'
            
            root = ''
            for i in obj:
                root +='-root %s '%( i )
                # print root
            
            Command = '-frameRange %s %s -uvWrite -attrPrefix xgen -worldSpace %s -stripNamespaces  -file %s'%( startTime, endTime, root, abcFile )
            mc.AbcExport( jobArg = Command )
        om.MGlobal.displayInfo( u'export patches for batch render： %s 已成功导出至 %s'%( xgenMa[0], path ) )
        message += '%s, '%( xgenMa[0] )
    mc.file( force=1, newFile=1 )
    if message:
        return message
    return True
#/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
def activeDirveCurve( File, dict ):
    '''
    读xgenPatch，根据dict激活guide或animwires;
    逐行查询关键字，找到第一个关键字，再往后逐行查询第二个关键字，以此类推，改起来非常绕。。。
    '''
    editLine = {}
    with open(File,'r') as f:
        lines = f.readlines()
    #先查询'Description\n'
    for index1, line1 in enumerate(lines):
        if line1 == 'Description\n':
            #再查询descriptionName，如果descriptionName存在于dict中继续
            for index2, line2 in enumerate(lines[index1+1:]):
                if '	name			' in line2:
                    descriptionName = line2[8:]
                    descriptionName = re.sub( '\n', '', descriptionName, 0 )
                    if descriptionName in dict:
                        #如果description以'guide'驱动
                        if dict[descriptionName] == 'guide':
                            #再查询'SplinePrimitive\n'
                            for index3, line3 in enumerate(lines[index1+index2+2:]):
                                if line3 == 'SplinePrimitive\n':
                                    #再查询'useCache'
                                    for index4, line4 in enumerate(lines[index1+index2+index3+3:]):
                                        if '	useCache		' in line4:
                                            if not line4[11:] == 'true\n':
                                                lineNum = index1+index2+index3+index4+4
                                                editLine[lineNum] = u'	useCache		true\n'
                                            #再查询'liveMode'
                                            for index5, line5 in enumerate(lines[index1+index2+index3+index4+4:]):
                                                if '	liveMode		' in line5:
                                                    if not line5[11:] == 'false\n':
                                                        lineNum = index1+index2+index3+index4+index5+5
                                                        editLine[lineNum] = u'	liveMode		false\n'
                                                    #再查询'cacheFileName'
                                                    for index6, line6 in enumerate(lines[index1+index2+index3+index4+index5+5:]):
                                                        if '	cacheFileName		' in line6:
                                                            if not line6[16:] == '${DESC}/guides.abc\n':
                                                                lineNum = index1+index2+index3+index4+index5+index6+6
                                                                editLine[lineNum] = u'	cacheFileName		${DESC}/guides.abc\n'
                                                            break
                                                    break
                                            break
                                    break
                        #如果description以'animWires'驱动
                        else:
                            #再查询AnimWiresFXModule
                            for index3, line3 in enumerate(lines[index1+index2+2:]):
                                if line3 == 'AnimWiresFXModule\n':
                                    #再查询'active'
                                    for index4, line4 in enumerate(lines[index1+index2+index3+3:]):
                                        if '	active			' in line4:
                                            if not line4[10:] == 'true\n':
                                                lineNum = index1+index2+index3+index4+4
                                                editLine[lineNum] = u'	active			true\n'
                                            #再查询'wiresFile'
                                            for index5, line5 in enumerate(lines[index1+index2+index3+index4+4:]):
                                                if '	wiresFile		' in line5:
                                                    if not line5[12:] == '${DESC}/${FXMODULE}/wires.abc\n':
                                                        lineNum = index1+index2+index3+index4+index5+5
                                                        editLine[lineNum] = u'	wiresFile		${DESC}/${FXMODULE}/wires.abc\n'
                                                    #再查询'liveMode'
                                                    for index6, line6 in enumerate(lines[index1+index2+index3+index4+index5+5:]):
                                                        if '	liveMode		' in line6:
                                                            if not line6[11:] == 'false\n':
                                                                lineNum = index1+index2+index3+index4+index5+index6+6
                                                                editLine[lineNum] = u'	liveMode		false\n'
                                                            break
                                                    break
                                            break
                                    break
                    break
    if editLine:
        with open(File,'r') as f:
            lines = f.readlines()
        with open(File,'w') as f_w:
            for index, line in enumerate(lines):
                if index in editLine:
                    newLine = editLine[index]
                    f_w.write(newLine)
                else:
                    f_w.write(line)
#/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
def editXgenAsset( fileName, newFileName, xgenPatchNames, newXgenPatchNames ):
    '''
    读ma，写ma，修改xgenPatch名称，清除ma文件中前缀为‘requires’字段的插件历史节点

    fileName               oldfile
    newFileName            newfile
    xgenPatchNames         patchList
    newXgenPatchNames      newPatchList
    '''
    #plugIn保留list
    #line存在list中的关键字则保留
    plugIn_list = ['maya "20',
                   '-nodeType',
                   'stereoCamera',
                   ]
    with open(fileName,'r') as f:
        lines = f.readlines()
    with open(newFileName,'w') as f_w:
        for index1, line in enumerate( lines ):
            try:
                #判断line是否删除
                Del = False
                if line[:8] == 'requires':
                    for i in plugIn_list:
                        if i in line:
                            Del = False
                            break
                        else:
                            Del = True
                if Del:
                    continue
                
                newline = ''
                for index2, xgenPatchName in enumerate( xgenPatchNames ):
                    if xgenPatchName in line:
                        newline = re.sub( xgenPatchName, newXgenPatchNames[index2], line, 0 )
                        break
                if newline:
                    f_w.write(newline)
                else:
                    f_w.write(line)
            except UnicodeDecodeError:
                f_w.write(line)
                om.MGlobal.displayInfo( u'editXgenAsset : 读取文件第 %s 行时，出现 UnicodeDecodeError'%(index1+1) )
#/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
def fix_root_offset( nurbsCurves, meshs, path, startTime ):
    '''
    修正曲线根部偏移，有一定操作局限，目前对于一个描述使用两个生长面不支持，可能会出错
    '''
    mc.currentTime( startTime, edit=True )
    import math
    #nurbsCurve命名规则: hair_lxy__short_hair_binjiao__guide__curve12
    
    #创建曲线对应的集合及描述的dict
    #dict = { collection:{ description:[ [ nurbsCurve, ... ], [ mesh, ... ] ], ... }, ... }
    dict = {}
    for nurbsCurve in nurbsCurves:
        split_nurbsCurve = re.split( '__', nurbsCurve )
        # 结果: ['hair_lxy', 'long_hair_back', 'guide', 'curve1'] # 
        if not len(split_nurbsCurve)==4:
            continue
        if not split_nurbsCurve[0] in dict:
            dict[ split_nurbsCurve[0] ] = { split_nurbsCurve[1]:[ [ nurbsCurve ], [] ] }
        else:
            if not split_nurbsCurve[1] in dict[ split_nurbsCurve[0] ]:
                dict[ split_nurbsCurve[0] ][ split_nurbsCurve[1] ] = [ [ nurbsCurve ], [] ]
            else:
                dict[ split_nurbsCurve[0] ][ split_nurbsCurve[1] ][0] += [ nurbsCurve ]
    # for c in dict:
    #     for d in dict[c]:
    #         print c,d,dict[c][d]

    #根据dict中的集合描述，查询本地文件 .xgen 的信息，找出growMesh
    '''
    xgen Patches 框架
    ------------------------------
    Patches
    ---------------------
    Patch	Subd
        name	growMesh
    Guides	Spline
        CVs
    endObject
    ---------------------
    Patch	Subd
        name	growMesh
    Guides	Spline
        CVs
    endObject
    ---------------------
    endPatches
    ------------------------------
    '''
    for c in dict:
        patch = ''
        for patchFile in os.listdir(path):
            if re.match('^.+__%s.xgen$'%(c),patchFile):
                patch = '%s/%s'%(path,patchFile)
                break
        if not patch:
            mc.warning( u'fix_root_offset: 集合 %s 未找到 patch, 已跳过！！'%(c) )
            continue
        
        with open( patch, 'r' ) as f:
            lines = f.readlines()
        for index1, line1 in enumerate(lines):
            if re.match( '^Patches	.+\n', line1 ):
                split_line1 = re.split( '\s+', line1 )
                if split_line1[1] in dict[c]:
                    growMeshs = []
                    for index2, line2 in enumerate(lines[index1+1:]):
                        if re.match( '^	name		.+\n', line2 ):
                            split_line2 = re.split( '\s+', line2 )
                            if split_line2[2] in meshs:
                                growMeshs.append( split_line2[2] )
                        elif re.match( 'endPatches\n', line2 ):
                            break
                    dict[c][ split_line1[1] ][1] = growMeshs

    for c in dict:
        for d in dict[c]:
            if dict[c][d][1]:
                # 目前只匹配第一个生长面，如果xgen生长面存在多个，后期需要修改
                meshShape = mc.listRelatives( dict[c][d][1][0], s=1 )[0]
                # 复制出来一个tempMesh
                mc.duplicate( dict[c][d][1][0], rr=1, n='tempMesh' )
                mc.makeIdentity( 'tempMesh', apply=1, t=1, r=1, s=1, n=0, pn=1 )
                tempMeshShape = mc.listRelatives( 'tempMesh', s=1 )[0]
                mc.blendShape( dict[c][d][1][0], 'tempMesh', w=(0, 1), origin='world' )
                # 创建 closestPointOnMesh 计算节点
                mc.createNode( 'closestPointOnMesh', n='closestPointOnMesh_temp' )
                mc.connectAttr( '%s.outMesh'%( tempMeshShape ), 'closestPointOnMesh_temp.inMesh', force=1 )
                for nurbsCurve in dict[c][d][0]:
                    # # 创建 pointCurveConstraint 约束曲线 ep[0]
                    # pointCurveConstraint = mc.pointCurveConstraint( '%s.ep[0]'%( nurbsCurve ), constructionHistory=True, replaceOriginal=True, w=1.0 )
                    # locShape = mc.listRelatives( pointCurveConstraint[0], s=1 )[0]
                    # point = mc.getAttr( '%s.localPosition'%( locShape ) )[0]
                    
                    # 获取曲线根位置
                    nurbsCurveShape = mc.listRelatives( nurbsCurve, s=1 )[0]
                    point = mc.xform( '%s.ep[0]'%( nurbsCurveShape ), q=1, ws=1, translation=1 )
                    # 传入参数至 'closestPointOnMesh_temp'，获取 UV 值
                    mc.setAttr( 'closestPointOnMesh_temp.inPositionX', point[0] )
                    mc.setAttr( 'closestPointOnMesh_temp.inPositionY', point[1] )
                    mc.setAttr( 'closestPointOnMesh_temp.inPositionZ', point[2] )
                    U = mc.getAttr( 'closestPointOnMesh_temp.result.parameterU' )
                    V = mc.getAttr( 'closestPointOnMesh_temp.result.parameterV' )
                    # 创建毛囊节点，并传入 UV 值
                    follicleShape = mc.createNode( 'follicle' )
                    mc.connectAttr( '%s.outMesh'%( meshShape ), '%s.inputMesh'%( follicleShape ), force=1 )
                    mc.connectAttr( '%s.worldMatrix'%( meshShape ), '%s.inputWorldMatrix'%( follicleShape ), force=1 )
                    mc.setAttr( '%s.parameterU'%( follicleShape ), U )
                    mc.setAttr( '%s.parameterV'%( follicleShape ), V )
                    follicleTransform = mc.listRelatives( follicleShape, p=1 )[0]
                    mc.connectAttr( '%s.outTranslate'%( follicleShape ), '%s.translate'%( follicleTransform ), force=1 )
                    mc.connectAttr( '%s.outRotate'%( follicleShape ), '%s.rotate'%( follicleTransform ), force=1 )
                    # 判断传入 UV 值后 follicle 是否在 Mesh 曲面上；如果不在，逐步+-值修正UV，计算出修正后里曲线根部最近的曲面 UV 值
                    follicleXYZ = mc.getAttr( '%s.translate'%( follicleTransform ) )[0]
                    if follicleXYZ==(0.0, 0.0, 0.0):
                        computation = {}
                        # U +
                        fix_U = U
                        fix_V = V
                        for index in range( 1000 ):
                            fix_U += 0.001
                            mc.setAttr( '%s.parameterU'%( follicleShape ), fix_U )
                            fix_follicleXYZ = mc.getAttr( '%s.translate'%( follicleTransform ) )[0]
                            if not fix_follicleXYZ==(0.0, 0.0, 0.0):
                                distance = math.hypot(math.hypot((fix_follicleXYZ[0]-point[0]), (fix_follicleXYZ[1]-point[1])), (fix_follicleXYZ[2]-point[2]))
                                computation[ distance ] = [ fix_U, fix_V ]
                                break
                            elif fix_U >= 1:
                                break
                        mc.setAttr( '%s.parameterU'%( follicleShape ), U )
                        # U -
                        fix_U = U
                        fix_V = V
                        for index in range( 1000 ):
                            fix_U -= 0.001
                            mc.setAttr( '%s.parameterU'%( follicleShape ), fix_U )
                            fix_follicleXYZ = mc.getAttr( '%s.translate'%( follicleTransform ) )[0]
                            if not fix_follicleXYZ==(0.0, 0.0, 0.0):
                                distance = math.hypot(math.hypot((fix_follicleXYZ[0]-point[0]), (fix_follicleXYZ[1]-point[1])), (fix_follicleXYZ[2]-point[2]))
                                computation[ distance ] = [ fix_U, fix_V ]
                                break
                            elif fix_U <= 0:
                                break
                        mc.setAttr( '%s.parameterU'%( follicleShape ), U )
                        # V +
                        fix_U = U
                        fix_V = V
                        for index in range( 1000 ):
                            fix_V += 0.001
                            mc.setAttr( '%s.parameterV'%( follicleShape ), fix_V )
                            fix_follicleXYZ = mc.getAttr( '%s.translate'%( follicleTransform ) )[0]
                            if not fix_follicleXYZ==(0.0, 0.0, 0.0):
                                distance = math.hypot(math.hypot((fix_follicleXYZ[0]-point[0]), (fix_follicleXYZ[1]-point[1])), (fix_follicleXYZ[2]-point[2]))
                                computation[ distance ] = [ fix_U, fix_V ]
                                break
                            elif fix_U >= 1:
                                break
                        mc.setAttr( '%s.parameterV'%( follicleShape ), V )
                        # V -
                        fix_U = U
                        fix_V = V
                        for index in range( 1000 ):
                            fix_V -= 0.001
                            mc.setAttr( '%s.parameterV'%( follicleShape ), fix_V )
                            fix_follicleXYZ = mc.getAttr( '%s.translate'%( follicleTransform ) )[0]
                            if not fix_follicleXYZ==(0.0, 0.0, 0.0):
                                distance = math.hypot(math.hypot((fix_follicleXYZ[0]-point[0]), (fix_follicleXYZ[1]-point[1])), (fix_follicleXYZ[2]-point[2]))
                                computation[ distance ] = [ fix_U, fix_V ]
                                break
                            elif fix_U <= 0:
                                break
                        mc.setAttr( '%s.parameterV'%( follicleShape ), V )
                        # 取最distance小值传入UV
                        if computation:
                            fix_UV = computation[ min(computation) ]
                            mc.setAttr( '%s.parameterU'%( follicleShape ), fix_UV[0] )
                            mc.setAttr( '%s.parameterV'%( follicleShape ), fix_UV[1] )
                            fix = True
                        else:
                            fix = False
                    else:
                        fix = True
                    # 创建 pointCurveConstraint 约束曲线 ep[0]
                    if fix:
                        pointCurveConstraint = mc.pointCurveConstraint( '%s.ep[0]'%( nurbsCurve ), constructionHistory=True, replaceOriginal=True, w=1.0 )
                        mc.parent( pointCurveConstraint[0], follicleTransform )
                    else:
                        mc.warning( u'fix_root_offset: %s 匹配不到合适的根部位置, 已跳过！！'%( nurbsCurve ) )
                mc.delete( 'closestPointOnMesh_temp', 'tempMesh' )
#/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
def editXgenPatchPath( fileName, newFileName, newXgDataPath ):
    '''
    读xgenPatch，写xgenPatch，修改xgDataPath
    '''
    with open(fileName,'r') as f:
        lines = f.readlines()
    with open(newFileName,'w') as f_w:
        xgDataPath = r'	xgDataPath		'+newXgDataPath+'\n'
        for index, line in enumerate( lines ):
            try:
                if line[:11] == r'	xgDataPath':
                    f_w.write(xgDataPath)
                else:
                    f_w.write(line)
            except UnicodeDecodeError:
                f_w.write(line)
                om.MGlobal.displayInfo( u'editXgenPatchPath : 读取文件第 %s 行时，出现 UnicodeDecodeError'%(index+1) )
#/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
def getAssetInfo( file, nameSpace ):
    '''
    根据提供的xgen资产路径，判断资产内容并返回导入资产需要的操作路径
    '''
    # 判断场景保存状态
    if not mc.file( q=1,sceneName=1 ):
        mc.warning( u'导入资产前，先保存场景,导入的xgen资产需要以当前场景路径保存,格式为 ma' )
        return None,None,None,None
    elif not mc.file( q=1,sceneName=1 )[-3:] == '.ma':
        mc.warning( u'当前场景文件格式不符合规范，请保存为 ma 格式' )
        return None,None,None,None
    
    # 获取当前场景文件路径，及输入的xgen资产路径
    maya_f = mc.file( q=1,sceneName=1 )
    xgen_asset = file
    xgen_patchs = []
    xgen_patchsName = []
    # 获取ma文件名
    assetName = re.sub( r'^.+/', '', xgen_asset, 0 )
    
    # 索引并生成当前cacheVer迭代版本
    cacheName = re.sub( '^xgen_', '', nameSpace, 0 )
    cacheVer = 'v01'
    cachePath = re.sub( r'/[^/]+\.ma$', '/PipelineCache/xgen/%s'%( cacheName ), maya_f, 0 )
    if os.path.exists(cachePath):
        cacheVerList = []
        for i in os.listdir(cachePath):
            if os.path.isdir( '%s/%s'%(cachePath,i) ) and re.match( '^v\d{2}$', i ):
                cacheVerList.append( int( re.sub( '^v', '', i, 0 ) ) )
        if cacheVerList:
            cacheVer = 'v%02d'%( max(cacheVerList)+1 )

    # 生成xgen_patch_RE
    xgen_patchRe = re.sub( r'\.ma$', '__.*\\.xgen$',assetName, 0 )
    xgen_patchRe = re.sub( r'^', '^',xgen_patchRe, 0 )
    # print xgen_patchRe
    # 结果: ^lxy_xgen__.*\.xgen$ #
    
    # 获取ma文件路径
    path = re.sub( r'/[^/]+\.ma$', '/', xgen_asset, 0 )
    # 查询ma文件路径下的所有文件
    for i in os.listdir(path):
        fullPath = os.path.join(path, i)
        # 判断是文件类型，排除文件夹
        if os.path.isfile(fullPath):
            # 匹配ma命名规则一样的xgen_patch，添加至列表
            if re.match( xgen_patchRe, i, flags=0 ):
                xgen_patchs.append(fullPath)
                xgen_patchsName.append(i)
    
    # 如果没找到xgen_patch，警告并退出
    if not xgen_patchs:
        mc.warning( u'当前资产文件没有找到 .xgen 补丁，检查资产是否正确' )
        return None,None,None,None
    
    XgDataPaths = []
    # 获取XgDataPaths文件夹路径
    for xgen_patch in xgen_patchs:
        with open( xgen_patch,"r") as f:
            lines = f.readlines()
            for line in lines:
                if line[:13] == r'	xgDataPath		':
                    if ';' in line or '${PROJECT}' in line:
                        mc.warning( u'当前资产文件 XgDataPath 不规范，不可以用相对路径 ${PROJECT} 或多重路径' )
                        return None,None,None,None
                    line = re.sub( r'\n$', r'', line[13:], 0 )
                    line = re.sub( r'\\', r'/', line, 0 )
                    line = re.sub( r'/$', r'', line, 0 )
                    XgDataPaths.append( line )
                    break
    # print XgDataPaths
    
    # 判断XgDataPath路径是否存在
    warningList = []
    for index, XgDataPath in enumerate( XgDataPaths ):
        if not os.path.exists(XgDataPath):
            warningList.append( xgen_patchsName[index] )
    if warningList:
        message = ''
        for i in warningList:
            message += i+' '
        mc.warning( u'当前资产中 %s 的 XgDataPath 路径未找到，检查资产 XgDataPath 路径是否存在'%( message ) )
        return None,None,None,None
    
    # 生成 newXgDataPaths 路径
    newXgDataPaths = []
    for XgDataPath in XgDataPaths:
        newXgDataPath=re.sub( '^.*/', '', XgDataPath, 0 )
        newXgDataPath=re.sub( '^', '%s/PipelineCache/xgen/%s/%s/collections/'%( re.sub( '/[^/]+\.ma$', '', maya_f, 0 ), cacheName, cacheVer ), newXgDataPath, 0 )
        newXgDataPaths.append( newXgDataPath )
    # print newXgDataPaths
    
    # # 生成temp文件(.ma,.xgen)路径
    # tempXgen_asset = re.sub( r'/[^/]+\.ma$', '/PipelineCache/xgen/%s/%s/temp/temp_asset.ma'%( cacheName, cacheVer ), maya_f, 0 )
    # tempXgen_patchs = []
    # for xgen_patchName in xgen_patchsName:
    #     tempXgen_patchName = re.sub( r'^%s'%( assetName[:-3] ), 'temp_asset', xgen_patchName, 0 )
    #     tempXgen_patch = re.sub( r'/[^/]+\.ma$', '/PipelineCache/xgen/%s/%s/temp/%s'%( cacheName, cacheVer, tempXgen_patchName ), maya_f, 0 )
    #     tempXgen_patchs.append( tempXgen_patch )
    # # print tempXgen_patchs
    # return xgen_asset, tempXgen_asset, xgen_patchs, tempXgen_patchs, XgDataPaths, newXgDataPaths

    return xgen_asset, xgen_patchs, XgDataPaths, newXgDataPaths
#/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
def importXgenAsset( file, nameSpace ):
    '''
    导入 xgen 资产到本地
    '''
    # get paths
    # xgen_asset, tempXgen_asset, xgen_patchs, tempXgen_patchs, XgDataPaths, newXgDataPaths = getAssetInfo( file, nameSpace )
    xgen_asset, xgen_patchs, XgDataPaths, newXgDataPaths = getAssetInfo( file, nameSpace )
    if not xgen_asset :
        return
    # print xgen_asset
    # print xgen_patchs
    # print XgDataPaths
    # print newXgDataPaths
    # return
    
    # mc.file( tempXgen_asset, i=1, namespace=nameSpace )
    mc.file( xgen_asset, namespace=nameSpace, type='mayaAscii', i=1, ignoreVersion=1, mergeNamespacesOnClash=0, renameAll=1, options='v=0', preserveReferences=1, importTimeRange='keep' )
    # 创建xgData路径
    for newXgDataPath in newXgDataPaths:
        if not os.path.exists(newXgDataPath):
            os.makedirs(newXgDataPath)
    # 修改xgDataPath
    for p in xg.palettes():
        if not 'XG_RENDER_' in p and re.match('^%s:.+$'%(nameSpace),p):
            collectionName = re.sub( '^.+:', '', p, 0 )
            modified = False
            for index,newXgDataPath in enumerate(newXgDataPaths):
                if re.match('.+%s$'%(collectionName),newXgDataPath):
                    xgData_dual = '%s;%s'%(newXgDataPath,XgDataPaths[index])
                    xgData_dual = xgData_dual.encode('gbk')
                    xg.setAttr( "xgDataPath", xgData_dual, p )
                    om.MGlobal.displayInfo( u'%s : xgDataPath modify successfully.'%(p) )
                    modified = True
                    break
            if not modified:
                om.MGlobal.displayInfo( u'%s : xgDataPath modify failed!!!!!!!!!!!!!!!'%(p) )
    # 修改xgen全局预览宽度
    setGlobalWidth(2)
    setPlayblastShader()
    # xgen pv off
    setXgenPreviewOff()
#/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
def confirmOverwriting( self, shotPath, nameSpaces ):
    '''
    导入 xgen 资产到本地时；判断本地缓存返回覆盖提示；

    return = True  表示继续；
    return = False 表示取消；
    '''
    result = True
    msgs = u''
    if os.path.exists(shotPath):
        for nameSpace in nameSpaces:
            cacheName = re.sub( '^xgen_', '', nameSpace, 0 )
            cachePath = '%s/PipelineCache/xgen/%s'%( shotPath, cacheName )
            if os.path.exists(cachePath):
                for ver in os.listdir(cachePath):
                    if re.match('^v\d{2}$',ver):
                        maxVer = re.sub( '^.+/', '', self.getMaxVerPath(cachePath), 0 )
                        msgs += u'%s  %s\n'%(nameSpace,maxVer)
                        break
    if msgs:
        from PySide2.QtWidgets import QMessageBox
        confirm = QMessageBox.question( self,
                                       u"Confirmation", u"以下 nameSpaces :\n\n%s\n已存在本地缓存，\n重新导入资产旧版本会被迭代！！\n\n是否继续？"%(msgs),
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes )
        if not confirm == QMessageBox.StandardButton.Yes:
            result = False
    return result
#/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
def reload_xgen_refenece( cache ):
    '''
    根据提供的dict，reload xgenCache
    '''
    scene_xgen = {}
    ref = mc.ls( type='reference' )

    # 排除此类来历不明的nameSpace
    # Result: ('XG_RENDER_:chr_lxy_default:hair_lxy', 'xgen_chr_lxy_default:hair_lxy') # 
    palettes = []
    for p in xg.palettes():
        if not 'XG_RENDER_' in p:
            palettes.append( p )
    
    for xgen in palettes:
        xgen_split = re.split( ':', xgen )
        if not xgen_split[0] in scene_xgen:
            scene_xgen[ xgen_split[0] ] = [ xgen ]
        else:
            scene_xgen[ xgen_split[0] ] += [ xgen ]
    
    # 如果文件已经保存则先删除patch，再从目标路径复制新的patch到scene路径
    sceneFile = mc.file( q=1,sceneName=1 )
    if sceneFile:
        if not sceneFile[-3:]=='.ma':
            mc.warning( u'reload 失败，请使用 ma 文件格式' )
            return
        sceneName = re.sub( '\.ma$', '', re.sub( '^.+/', '', sceneFile, 0 ), 0 )
        path = re.sub( '/[^/]+$', '', sceneFile, 0 )
        for xgen in cache:
            if xgen in scene_xgen and '%sRN'%xgen in ref:
                for p in scene_xgen[xgen]:
                    patchName = mc.getAttr( '%s.xgFileName'%( p ) )
                    patchFile = '%s/%s'%( path, patchName )
                    if os.path.isfile( patchFile ):
                        os.remove( patchFile )
                
                reloadFile = cache[xgen]
                reloadFileName = re.sub( '\.ma$', '', re.sub( '^.+/', '', reloadFile, 0 ), 0 )
                reloadPath = re.sub( '/[^/]+$', '', reloadFile, 0 )
                reloadPatchFileName = []
                reloadPatchFile = []
                for f in os.listdir( reloadPath ):
                    # chr_lxy_default__hair_lxy.xgen
                    if re.match( '^%s__.+\.xgen$'%( reloadFileName ), f ):
                        reloadPatchFileName.append( f )
                        reloadPatchFile.append( '%s/%s'%( reloadPath, f ) )
                
                # render_jigong_003A_003_v02__chr_lxy_default__hair_lxy.xgen
                newPatchFileName = []
                newPatchFile = []
                for patch in reloadPatchFileName:
                    newPatchFileName.append( '%s__%s__%s'%( sceneName, xgen, re.sub( '%s__'%( reloadFileName ), '', patch, 0 ) ) )
                    newPatchFile.append( '%s/%s__%s__%s'%( path, sceneName, xgen, re.sub( '%s__'%( reloadFileName ), '', patch, 0 ) ) )
                for index, patch in enumerate( reloadPatchFile ):
                    shutil.copyfile( patch, newPatchFile[index] )
    
    for xgen in cache:
        if xgen in scene_xgen and '%sRN'%xgen in ref:
            mc.file( unloadReference='%sRN'%xgen )
            mc.file( cache[xgen], loadReference='%sRN'%xgen )
#/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
def dirlist(path,allfile=[]):
    '''
    递归文件列表
    '''
    filelist =  os.listdir(path)
    for filename in filelist:
        filepath = os.path.join(path, filename)
        if os.path.isdir(filepath):
            dirlist(filepath, allfile)
        else:
            allfile.append(filepath)
    return allfile
#/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////





















#/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

# def writeNote(user,note,file):
#     '''
#     此方法不支持写入中文字符
#     '''
#     import json
#     import time
#     date = time.strftime( "%Y-%m-%d %H:%M:%S" )
#     dict =  {
#     "account":user,
#     "lastversion":[],
#     "description":note,
#     "time":date
#     }
#     path = re.sub('/[^/]+$','',file)
#     if not os.path.exists( path ):
#         os.makedirs( path )
#     with open( file.decode('utf-8'), "w" ) as f:
#         json.dump( dict, f, indent=4 )
#     return file

def writeNote(user,note,file):
    '''
    支持写入中文字符
    '''
    import json
    import codecs
    import time
    date = time.strftime( "%Y-%m-%d %H:%M:%S" )
    dict =  { "account":user, "lastversion":[], "description":note, "time":date, }
    path = re.sub('/[^/]+$','',file)
    if not os.path.exists( path ):
        os.makedirs( path )
    f = codecs.open(file, 'w', 'utf-8')
    f.write(json.dumps(dict,f,indent=4,ensure_ascii=False))
    f.close()
    return file

def getTask(task):
    '''
    获取用户名
    传入任务名，获取任务状态
    '''
    import sys
    scriptsPath='Z:/Resource/Tool/pms/pyapi'
    if not scriptsPath in sys.path:
        sys.path.append(scriptsPath)
    import pms
    user = pms.get_user_info()['useraccount']
    # task = pms.get_user_task_list('stmh',user)
    taskState = pms.get_task_state(task)
    return user,taskState

#/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
def editFilePath( file, newFile, path, newPath ):
    '''
    读file，写newFile;
    清除ma文件中前缀为‘requires’字段的插件历史节点;
    修改file中的关键字段path为newPath;
    '''
    # plugIn保留list
    # line存在list中的关键字则保留
    plugIn_list = ['maya "20',
                   '-nodeType',
                   'stereoCamera',
                   ]
    with open(file,'r') as f:
        lines = f.readlines()
    with open(newFile,'w') as f_w:
        for index, line in enumerate( lines ):
            try:
                #判断line是否删除
                Del = False
                if line[:8] == 'requires':
                    for plugIn in plugIn_list:
                        if plugIn in line:
                            Del = False
                            break
                        else:
                            Del = True
                if Del:
                    continue
                # 判断line是否需要修改路径
                if path in line:
                    newLine = re.sub( path, newPath, line, 0 )
                    f_w.write(newLine)
                else:
                    f_w.write(line)
            except UnicodeDecodeError:
                # 通常try部分出错都是中文编码问题，如果出错则照搬这一行过去不做改动
                f_w.write(line)
                om.MGlobal.displayInfo( u'editFilePath : 读取文件第 %s 行时，出现 UnicodeDecodeError'%(index+1) )
#/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
def publish(self):
    '''
    以下是上传前需要确定的缓存路径信息
    G:/py/testPath/publish_path/SC000/SC000_Ca013/cache/cfx/xgen/chr_lxy_new/v01
    '''
    cfxCachePreviewPath = 'Z:/Cache/Cfx/Preview' # 此路径用于汇总cfx的项目相关拍屏，每次提交镜头时，拍屏先拷贝至此
    pipelineProject = ['stmh','test','bk'] # 判断如果当前项目为列表中的项目，则执行谜谭上传端口
    pro = self.comboBox_Project.currentText()
    ep = self.comboBox_Ep.currentText()
    shot = self.comboBox_Shot.currentText()
    if not shot:
        mc.warning( u'未选择有效镜头号，或未设置 Preference：Project path' )
        return
    publishPath = self.pro.publishPath(ep,shot)
    #G:/py/testPath/publish_path/SC000/SC000_Ca013/cache/cfx
    
    
    #[ cacheName, ... ]
    packages,publishCaches = getSelected(self)
    xgenCacheFlies = getCaches(self)
    message = ''
    if pro not in pipelineProject:
        pass
    else:
        # 对应谜谭提交的专属定制，下游端口内容比较混乱
        task = '%s_%s_%s_cfx_hair'%(pro,ep,shot)
        user,taskState = getTask(task)
        # task = 'test_050_0020_cfx_hair'
        publishState = ['ip','cp']
        if pro == 'stmh' or pro == 'bk':
            if not taskState in publishState:
                mc.warning( u'%s : 任务状态为 %s，详情资讯制片小姐姐。'%(task,taskState) )
                return
        tempPath = 'D:/pub_temp/shot'
        xgenPublishPath = '%s/hair'%(publishPath)
        pubVer = 'v01'
        if os.path.exists(xgenPublishPath):
            pubVerList = []
            for v in os.listdir(xgenPublishPath):
                if re.match( '^v\d{2}$', v ):
                    pubVerList.append( int( v[-2:] ) )
            if pubVerList:
                pubVer = 'v%02d'%(max(pubVerList)+1)
        
        # 启用 ui 对话框，选择 pv 文件，输入 note
        cacheNames = []
        for cacheName, locCacheVer, simAbc, driveMesh, xgenFiles, xgenAbcs in xgenCacheFlies:
            cacheNames.append(cacheName)
        confirm,preview,note = self.launch_shotPublishInfo(task,cacheNames)
        # 对话框返回值如果未确认则退出
        if not confirm:
            return
        
        # 生成 cacheFileDict
        cacheFileDict = {}
        #[ [ xgenCacheName, ver, simAbc, xgenDriveMesh, [ xgenMa, xgenPatchs, xgenCollectionsPath ], xgenAbcs ], ... ]
        for cacheName, locCacheVer, simAbc, driveMesh, xgenFiles, xgenAbcs in xgenCacheFlies:
            cacheNameSplit = re.split('_',cacheName)
            pubCacheName = '%s_%s_%s'%(pro,cacheNameSplit[0],cacheNameSplit[1])
            customVerName = re.sub( '^%s_'%('%s_%s'%(cacheNameSplit[0],cacheNameSplit[1])), '', cacheName )
            # print( cacheName, locCacheVer, simAbc, driveMesh, xgenFiles, xgenAbcs )
            # 本地和提交路径
            localCachePath = re.sub('/[^/]+$','',xgenFiles[0])
            pubCachePath = '%s/%s/%s/xgen/%s'%(xgenPublishPath,pubVer,pubCacheName,customVerName)
            # 修改ma路径，并写入到tempPub路径下
            maFileName = re.sub('^.+/','',xgenFiles[0])
            maTempFile = '%s/%s/%s'%(tempPath,task,maFileName)
            if not os.path.exists('%s/%s'%(tempPath,task)):
                os.makedirs('%s/%s'%(tempPath,task))
            editFilePath( xgenFiles[0], maTempFile, localCachePath, pubCachePath )
            # 修改patchs路径，并写入到tempPub路径下
            xgenTempPatchs = []
            for xgenPatch in xgenFiles[1]:
                xgenPatchName = re.sub('^.+/','',xgenPatch)
                xgenTempPatch = '%s/%s/%s'%(tempPath,task,xgenPatchName)
                editFilePath( xgenPatch, xgenTempPatch, localCachePath, pubCachePath )
                # 上传前检查设置全局宽度
                editGlobalWidth(1,xgenTempPatch)
                xgenTempPatchs.append(xgenTempPatch)
            xgenCacheFile = [maTempFile]+xgenTempPatchs+[xgenFiles[2]]+xgenAbcs
            if pubCacheName not in cacheFileDict:
                cacheFileDict[pubCacheName] = {customVerName:xgenCacheFile}
            else:
                if customVerName not in cacheFileDict[pubCacheName]:
                    cacheFileDict[pubCacheName][customVerName] = xgenCacheFile
        if cacheFileDict:
            # 开始写 json 至本地临时目录
            noteFile = '%s/%s/%s.json'%(tempPath,task,task)
            writeNote(user,note,noteFile)
            # 复制提交拍屏至 cfxCache 汇总路径
            pvFormat = re.sub('^.+\.','',preview)
            cfxCachePreview = '%s/%s/%s/%s_%s_%s_cfx_hair.%s'%(cfxCachePreviewPath,pro,ep,pro,ep,shot,pvFormat)
            cfxCachePreviewExactPath = '%s/%s/%s'%(cfxCachePreviewPath,pro,ep)
            if not os.path.exists(cfxCachePreviewExactPath):
                os.makedirs( cfxCachePreviewExactPath )
            shutil.copyfile( preview, cfxCachePreview )
            # 添加汇总路径的拍屏至提交 dict
            for k1 in cacheFileDict:
                for k2 in cacheFileDict[k1]:
                    cacheFileDict[k1][k2] += [cfxCachePreview,noteFile]
                    break
                break
            
            # publish
            import sys
            scriptsPath='Z:/Resource/Tool/pub'
            if not scriptsPath in sys.path:
                sys.path.append(scriptsPath)
            print( task )
            print( '-------------------------------------------------------------------------' )
            for k1 in cacheFileDict:
                print( k1 )
                for k2 in cacheFileDict[k1]:
                    print( k2 )
                    for f in cacheFileDict[k1][k2]:
                        print( f )
            print( '-------------------------------------------------------------------------' )
            # return
            import pub_cfx_shot
            reload(pub_cfx_shot)
            pub_cfx_shot.cfx_shot_copy(task,'xgen',cacheFileDict)
            print( 'done' )
            try:
                shutil.rmtree(tempPath)
            except Exception:
                import traceback
                # traceback.print_exc()
                mc.warning( u'操作失败!\n%s'%traceback.format_exc())
    '''
    xgen
    task = 'stmh_150_0020_cfx_hair'
    cacheType = 'xgen'
    cacheFile = {cacheName:{xgenCacheName:[maFile,xgenFiles,abcFiles,collectionsFolder,note.json],... },...}
    '''
    '''
    xgen
    task = 'stmh_150_0020_cfx_hair'
    cacheType = 'xgen'
    cacheFile = {'stmh_chr_Wukong':{'chr_Wukong_default':["Z:/Cache/Cfx/Projects/moyaoan/stmh/shot/000/0010/maya/PipelineCache/xgen/chr_Wukong_default/v01/chr_Wukong_default.ma",
                                                          "Z:/Cache/Cfx/Projects/moyaoan/stmh/shot/000/0010/maya/PipelineCache/xgen/chr_Wukong_default/v01/chr_Wukong_default__Wukong.xgen",
                                                          "Z:/Cache/Cfx/Projects/moyaoan/stmh/shot/000/0010/maya/PipelineCache/xgen/chr_Wukong_default/v01/chr_Wukong_default__Wukong.abc",
                                                          "Z:/Cache/Cfx/Projects/moyaoan/stmh/shot/000/0010/maya/PipelineCache/xgen/chr_Wukong_default/v01/collections",
                                                          "Z:/Cache/Cfx/Projects/moyaoan/stmh/shot/000/0010/maya/Preview/stmh_000_0130_cfx_hair.mov",
                                                          "Z:/Cache/Cfx/Projects/moyaoan/stmh/shot/000/0010/maya/note.json"],
                                    'chr_Wukong_defaultA':["Z:/Cache/Cfx/Projects/moyaoan/stmh/shot/000/0010/maya/PipelineCache/xgen/chr_Wukong_defaultA/v01/chr_Wukong_defaultA.ma",
                                                           "Z:/Cache/Cfx/Projects/moyaoan/stmh/shot/000/0010/maya/PipelineCache/xgen/chr_Wukong_defaultA/v01/chr_Wukong_defaultA__Wukong.xgen",
                                                           "Z:/Cache/Cfx/Projects/moyaoan/stmh/shot/000/0010/maya/PipelineCache/xgen/chr_Wukong_defaultA/v01/chr_Wukong_defaultA__Wukong.abc",
                                                           "Z:/Cache/Cfx/Projects/moyaoan/stmh/shot/000/0010/maya/PipelineCache/xgen/chr_Wukong_defaultA/v01/collections"] },
                 
                 'stmh_chr_BaJie':{'chr_BaJie_default':["Z:/Cache/Cfx/Projects/moyaoan/stmh/shot/000/0010/maya/PipelineCache/xgen/chr_BaJie_default/v01/chr_BaJie_default.ma",
                                                        "Z:/Cache/Cfx/Projects/moyaoan/stmh/shot/000/0010/maya/PipelineCache/xgen/chr_BaJie_default/v01/chr_BaJie_default__Wukong.xgen",
                                                        "Z:/Cache/Cfx/Projects/moyaoan/stmh/shot/000/0010/maya/PipelineCache/xgen/chr_BaJie_default/v01/chr_BaJie_default__Wukong.abc",
                                                        "Z:/Cache/Cfx/Projects/moyaoan/stmh/shot/000/0010/maya/PipelineCache/xgen/chr_BaJie_default/v01/collections"],
                                    'chr_BaJie_defaultA':["Z:/Cache/Cfx/Projects/moyaoan/stmh/shot/000/0010/maya/PipelineCache/xgen/chr_BaJie_defaultA/v01/chr_BaJie_defaultA.ma",
                                                          "Z:/Cache/Cfx/Projects/moyaoan/stmh/shot/000/0010/maya/PipelineCache/xgen/chr_BaJie_defaultA/v01/chr_BaJie_defaultA__Wukong.xgen",
                                                          "Z:/Cache/Cfx/Projects/moyaoan/stmh/shot/000/0010/maya/PipelineCache/xgen/chr_BaJie_defaultA/v01/chr_BaJie_defaultA__Wukong.abc",
                                                          "Z:/Cache/Cfx/Projects/moyaoan/stmh/shot/000/0010/maya/PipelineCache/xgen/chr_BaJie_defaultA/v01/collections"] }
                }
    '''


#/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////



































# #/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# #弃用
# #读xgenPatch 修改FXModule active
# def activeFXModule( File ):
#     editLine = []
#     with open(File,'r') as f:
#         lines = f.readlines()
#     for index, line in enumerate(lines):
#         if 'FXModule\n' in line:
#             if 'false' in lines[index+1]:
#                 editLine.append(index+1)
    
#     with open(File,'r') as f:
#         lines = f.readlines()
#     with open(File,'w') as f_w:
#         for index, line in enumerate(lines):
#             if index in editLine:
#                 #print index+1
#                 #print line
#                 newLine = re.sub( 'false', 'true', line, 0 )
#                 f_w.write(newLine)
#             else:
#                 f_w.write(line)

#/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////








