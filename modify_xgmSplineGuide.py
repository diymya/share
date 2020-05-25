# -*- coding: utf-8 -*-
# ---------------------------------- #
#   Author: Morris                   #
#     Mail: 58411395@qq.com          #
#     Date: 2018/6/1                 #
# ---------------------------------- #
# 编辑xgenGuide工具
# 整合maya中蹩脚的guide编辑菜单
# ---------------------------------- #

import maya.cmds as mc
import maya.mel as mel

# --------------------------------------------------------------------------------------
def setXgmGuide( blendValue, taperValue, widthValue ):
    if len(mc.ls( sl=1 ))==0:
        for i in mc.ls( type='xgmSplineGuide' ):
            mc.setAttr( i+'.blend', blendValue )
            mc.setAttr( i+'.taper', taperValue )
            mc.setAttr( i+'.width', widthValue )
    else:
        objs=mc.ls( sl=1 )
        for i in objs:
            mc.setAttr( i+'.blend', blendValue )
            mc.setAttr( i+'.taper', taperValue )
            mc.setAttr( i+'.width', widthValue )

# --------------------------------------------------------------------------------------
def modify_xgmSplineGuide():
    blendValue=mc.floatField( 'hh_tf',q=1,v=1)
    taperValue=mc.floatField('zh_tf',q=1,v=1)
    widthValue=mc.floatField('kd_tf',q=1,v=1)
    setXgmGuide( blendValue, taperValue, widthValue)

# --------------------------------------------------------------------------------------
def rebuild_XgenCVCount():
    mytext1 = mc.intField('mytext1',q=1 ,v=1)
    PontNum = mytext1 
    mel.eval('xgmChangeCVCount('+str(PontNum)+')')

# --------------------------------------------------------------------------------------
def xgmNormalizeGuides():
    mel.eval('xgmNormalizeGuides()')

# --------------------------------------------------------------------------------------
def rebuild_XgenCVCountNum(int):
    mel.eval('xgmChangeCVCount('+str(int)+')')

# --------------------------------------------------------------------------------------
def UI():
    name='modifyXgmSplineGuideUI'
    
    if mc.window(name,ex=1):
        mc.deleteUI(name)
    mc.window(name)
    mc.window(name,e=1,s=0,wh=[150,245])
    
    mc.rowColumnLayout('top_rcl',nc=1)
    mc.rowColumnLayout(nc=2,p='top_rcl')
    mc.text(u'      混合')
    mc.floatField('hh_tf',v=0.0,precision=1)
    mc.text(u'      锥化')
    mc.floatField('zh_tf',v=0.2,precision=1)
    mc.text(u'      宽度')
    mc.floatField( 'kd_tf',v=0.01,precision=2)
    
    mc.rowColumnLayout(nc=1,p='top_rcl')
    mc.button(l=u'修改',w=145,c=lambda *args: modify_xgmSplineGuide())

    mc.separator()
    mc.separator()
    
    mc.rowColumnLayout(nc=3,p='top_rcl',columnOffset=[2,'both',5],rowOffset=[2,'both',5])
    mc.button(l=u'5',c=lambda *args: rebuild_XgenCVCountNum(5),w=45)
    mc.button(l=u'6',c=lambda *args: rebuild_XgenCVCountNum(6),w=45)
    mc.button(l=u'7',c=lambda *args: rebuild_XgenCVCountNum(7),w=45)
    mc.button(l=u'8',c=lambda *args: rebuild_XgenCVCountNum(8),w=45)
    mc.button(l=u'9',c=lambda *args: rebuild_XgenCVCountNum(9),w=45)
    mc.button(l=u'10',c=lambda *args: rebuild_XgenCVCountNum(10),w=45)

    
    mc.rowColumnLayout(nc=1,p='top_rcl',columnOffset=[2,'both',5])
    mc.separator()
    
    mc.rowColumnLayout(nc=3,p='top_rcl',columnOffset=[2,'both',5])
    mc.text(u'  点数:')
    mc.intField('mytext1',v=11,w=40)
    mc.button(l=u'重建',c=lambda *args: rebuild_XgenCVCount(),w=60)
    
    mc.rowColumnLayout(nc=1,p='top_rcl')
    mc.separator()
    mc.separator()
    mc.button(l=u'规格化',c=lambda *args: xgmNormalizeGuides(),w=145)
    
    mc.showWindow()
# --------------------------------------------------------------------------------------
UI()