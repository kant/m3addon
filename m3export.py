#!/usr/bin/python3
# -*- coding: utf-8 -*-

# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

if "bpy" in locals():
    import imp
    if "generateM3Library" in locals():
        imp.reload(generateM3Library)
from . import generateM3Library
generateM3Library.generateM3Library()

if "bpy" in locals():
    import imp
    if "m3" in locals():
        imp.reload(m3)
    if "shared" in locals():
        imp.reload(shared)

from . import m3
from . import shared
import bpy
import mathutils
import os.path

actionTypeScene = "SCENE"

class Exporter:
    def exportParticleSystems(self, scene, m3FileName):
        self.generatedAnimIdCounter = 0
        self.scene = scene
        if scene.render.fps != 30:
            print("Warning: It's recommended to export models with a frame rate of 30 (current is %s)" % scene.render.fps)
        self.nameToAnimIdToAnimDataMap = {}
        for animation in scene.m3_animations:
            self.nameToAnimIdToAnimDataMap[animation.name] = {}
        
        model = self.createModel(m3FileName)
        m3.saveAndInvalidateModel(model, m3FileName)

    def createModel(self, m3FileName):
        model = m3.MODLV23()
        model.modelName = os.path.basename(m3FileName)
        model.flags = 0x80d53
        
        model.nSkinBones = 0
        model.vFlags = 0x180007d # no vertices
        model.divisions = [self.createEmptyDivision()]
        model.boundings = self.createAlmostEmptyBoundingsWithRadius(2.0)
        
        self.initMaterials(model)
        self.initParticles(model)
        self.prepareAnimationEndEvents()
        self.initWithPreparedAnimationData(model)
        
        model.matrix = self.createIdentityMatrix()
        model.uniqueUnknownNumber = 0
        return model
    
    def frameToMS(self, frame):
        frameRate = self.scene.render.fps
        return round((frame / frameRate) * 1000.0)
    
    def prepareAnimationEndEvents(self):
        scene = self.scene
        for animation in scene.m3_animations:
            animIdToAnimDataMap = self.nameToAnimIdToAnimDataMap[animation.name]
            animEndId = 0x65bd3215
            animIdToAnimDataMap[animEndId] = self.createAnimationEndEvent(animation)
    
    def createAnimationEndEvent(self, animation):
        event = m3.SDEVV0()
        event.frames = [self.frameToMS(animation.endFrame)]
        event.flags = 1
        event.fend = self.frameToMS(animation.endFrame)
        event.keys = [self.createAnimationEndEventKey(animation)]
        return event
        
    def createAnimationEndEventKey(self, animation):
        event = m3.EVNTV1()
        event.name = "Evt_SeqEnd"
        event.matrix = self.createIdentityMatrix()
        return event
    
    def initWithPreparedAnimationData(self, model):
        scene = self.scene
        for animation in scene.m3_animations:
            animIdToAnimDataMap = self.nameToAnimIdToAnimDataMap[animation.name]
            animIds = list(animIdToAnimDataMap.keys())
            animIds.sort()
            
            m3Sequence = m3.SEQSV1()
            m3Sequence.name = animation.name
            m3Sequence.animStartInMS = self.frameToMS(animation.startFrame)
            m3Sequence.animEndInMS = self.frameToMS(animation.endFrame)
            m3Sequence.movementSpeed = animation.movementSpeed
            m3Sequence.setNamedBit("flags", "notLooping", animation.notLooping)
            m3Sequence.setNamedBit("flags", "alwaysGlobal", animation.alwaysGlobal)
            m3Sequence.setNamedBit("flags", "globalInPreviewer", animation.globalInPreviewer)
            m3Sequence.frequency = animation.frequency
            m3Sequence.boundingSphere = self.createAlmostEmptyBoundingsWithRadius(2)
            seqIndex = len(model.sequences)
            model.sequences.append(m3Sequence)
            
            m3SequenceTransformationGroup = m3.STG_V0()
            m3SequenceTransformationGroup.name = animation.name
            stcIndex = len(model.sequenceTransformationCollections)
            m3SequenceTransformationGroup.stcIndices = [stcIndex]
            stgIndex = len(model.sequenceTransformationGroups)
            model.sequenceTransformationGroups.append(m3SequenceTransformationGroup)
            
            m3SequenceTransformationCollection = m3.STC_V4()
            m3SequenceTransformationCollection.name = animation.name + "_full"
            m3SequenceTransformationCollection.seqIndex = seqIndex
            m3SequenceTransformationCollection.stgIndex = stgIndex
            m3SequenceTransformationCollection.animIds = list(animIds)
            for animId in animIds:
                animData = animIdToAnimDataMap[animId]
                self.addAnimDataToTransformCollection(animData, m3SequenceTransformationCollection)
            model.sequenceTransformationCollections.append(m3SequenceTransformationCollection)

            m3STS = m3.STS_V0()
            m3STS.animIds = list(animIds)
            model.sts.append(m3STS)
    
    def addAnimDataToTransformCollection(self, animData, m3SequenceTransformationCollection):
        animDataType = type(animData)
        if animDataType == m3.SDEVV0:
            sdevIndex = len(m3SequenceTransformationCollection.sdev)
            m3SequenceTransformationCollection.sdev.append(animData)
            #sdev's have animation type index 0, so sdevIndex = animRef
            animRef = sdevIndex
        elif animDataType == m3.SD2VV0:
            sd2vIndex = len(m3SequenceTransformationCollection.sd2v)
            m3SequenceTransformationCollection.sd2v.append(animData)
            animRef = 0x10000 + sd2vIndex
        elif animDataType == m3.SD3VV0:
            sd3vIndex = len(m3SequenceTransformationCollection.sd3v)
            m3SequenceTransformationCollection.sd3v.append(animData)
            animRef = 0x20000 + sd3vIndex
        elif animDataType == m3.SD4QV0:
            sd4qIndex = len(m3SequenceTransformationCollection.sd4q)
            m3SequenceTransformationCollection.sd4q.append(animData)
            animRef = 0x30000 + sd4qIndex
        elif animDataType == m3.SDR3V0:
            sdr3Index = len(m3SequenceTransformationCollection.sdr3)
            m3SequenceTransformationCollection.sdr3.append(animData)
            animRef = 0x50000 + sdr3Index
        elif animDataType == m3.SDS6V0:
            sds6Index = len(m3SequenceTransformationCollection.sds6)
            m3SequenceTransformationCollection.sds6.append(animData)
            animRef = 0x50000 + sds6Index
        else:
            raise Exception("Can't handle animation data of type %s yet" % animDataType)
        m3SequenceTransformationCollection.animRefs.append(animRef)

    def initParticles(self, model):
        scene = self.scene
        for particleSystemIndex, particleSystem in enumerate(scene.m3_particle_systems):
            boneName = "Star2Part" + particleSystem.boneSuffix
            boneIndex = len(model.bones)
            bone = self.createStaticBoneAtOrigin(boneName)
            model.bones.append(bone)
            boneRestPos = self.createIdentityRestPosition()
            model.absoluteInverseBoneRestPositions.append(boneRestPos)
            m3ParticleSystem = m3.PAR_V12()
            m3ParticleSystem.bone = boneIndex
            animPathPrefix = "m3_particle_systems[%s]." % particleSystemIndex
            transferer = BlenderToM3DataTransferer(exporter=self, m3Object=m3ParticleSystem, blenderObject=particleSystem, animPathPrefix=animPathPrefix, actionOwnerName=self.scene.name, actionOwnerType=actionTypeScene)
            transferer.transferAnimatableFloat("initEmissSpeed")
            transferer.transferAnimatableFloat("speedVar")
            transferer.transferBoolToInt("speedVarEnabled")
            transferer.transferAnimatableFloat("angleY")
            transferer.transferAnimatableFloat("angleX")
            transferer.transferAnimatableFloat("speedX")
            transferer.transferAnimatableFloat("speedY")
            transferer.transferAnimatableFloat("lifespan")
            transferer.transferAnimatableFloat("decay")
            transferer.transferBoolToInt("decayEnabled")
            transferer.transferFloat("emissSpeed2")
            transferer.transferFloat("scaleRatio")
            transferer.transferFloat("unknownFloat1a")
            transferer.transferFloat("unknownFloat1b")
            transferer.transferFloat("unknownFloat1c")
            transferer.transferAnimatableVector3("pemitScale")
            transferer.transferAnimatableVector3("speedUnk1")
            transferer.transferAnimatableColor("color1a")
            transferer.transferAnimatableColor("color1b")
            transferer.transferAnimatableColor("color1c")
            transferer.transferFloat("emissSpeed3")
            transferer.transferFloat("unknownFloat2a")
            transferer.transferFloat("unknownFloat2b")
            transferer.transferFloat("unknownFloat2c")
            transferer.transferBoolToInt("trailingEnabled")
            m3ParticleSystem.indexPlusHighestIndex = len(scene.m3_particle_systems) -1 + particleSystemIndex
            transferer.transferInt("maxParticles")
            transferer.transferAnimatableFloat("emissRate")
            transferer.transferEnum("type")
            transferer.transferAnimatableVector3("emissArea")
            transferer.transferAnimatableVector3("tailUnk1")
            transferer.transferAnimatableFloat("pivotSpread")
            transferer.transferAnimatableFloat("spreadUnk")
            transferer.transferBoolToInt("radialEmissionEnabled")
            transferer.transferBoolToInt("pemitScale2Enabled")
            transferer.transferAnimatableVector3("pemitScale2")
            transferer.transferBoolToInt("pemitRotateEnabled")
            transferer.transferAnimatableVector3("pemitRotate")
            transferer.transferBoolToInt("color2Enabled")
            transferer.transferAnimatableColor("color2a")
            transferer.transferAnimatableColor("color2b")
            transferer.transferAnimatableColor("color2c")
            transferer.transferAnimatableUInt16("partEmit")
            m3ParticleSystem.speedUnk2 = self.createNullVector4As4uint8()
            transferer.transferFloat("lifespanRatio")
            transferer.transferInt("columns")
            transferer.transferInt("rows")
            m3ParticleSystem.setNamedBit("flags", "sort", particleSystem.sort)
            m3ParticleSystem.setNamedBit("flags", "collideTerrain", particleSystem.collideTerrain)
            m3ParticleSystem.setNamedBit("flags", "collideObjects", particleSystem.collideObjects)
            m3ParticleSystem.setNamedBit("flags", "spawnOnBounce", particleSystem.spawnOnBounce)
            m3ParticleSystem.setNamedBit("flags", "useInnerShape", particleSystem.useInnerShape)
            m3ParticleSystem.setNamedBit("flags", "inheritEmissionParams", particleSystem.inheritEmissionParams)
            m3ParticleSystem.setNamedBit("flags", "inheritParentVel", particleSystem.inheritParentVel)
            m3ParticleSystem.setNamedBit("flags", "sortByZHeight", particleSystem.sortByZHeight)
            m3ParticleSystem.setNamedBit("flags", "reverseIteration", particleSystem.reverseIteration)
            m3ParticleSystem.setNamedBit("flags", "smoothRotation", particleSystem.smoothRotation)
            m3ParticleSystem.setNamedBit("flags", "bezSmoothRotation", particleSystem.bezSmoothRotation)
            m3ParticleSystem.setNamedBit("flags", "smoothSize", particleSystem.smoothSize)
            m3ParticleSystem.setNamedBit("flags", "bezSmoothSize", particleSystem.bezSmoothSize)
            m3ParticleSystem.setNamedBit("flags", "smoothColor", particleSystem.smoothColor)
            m3ParticleSystem.setNamedBit("flags", "bezSmoothColor", particleSystem.bezSmoothColor)
            m3ParticleSystem.setNamedBit("flags", "litParts", particleSystem.litParts)
            m3ParticleSystem.setNamedBit("flags", "randFlipBookStart", particleSystem.randFlipBookStart)
            m3ParticleSystem.setNamedBit("flags", "multiplyByGravity", particleSystem.multiplyByGravity)
            m3ParticleSystem.setNamedBit("flags", "clampTailParts", particleSystem.clampTailParts)
            m3ParticleSystem.setNamedBit("flags", "spawnTrailingParts", particleSystem.spawnTrailingParts)
            m3ParticleSystem.setNamedBit("flags", "useVertexAlpha", particleSystem.useVertexAlpha)
            m3ParticleSystem.setNamedBit("flags", "modelParts", particleSystem.modelParts)
            m3ParticleSystem.setNamedBit("flags", "swapYZonModelParts", particleSystem.swapYZonModelParts)
            m3ParticleSystem.setNamedBit("flags", "scaleTimeByParent", particleSystem.scaleTimeByParent)
            m3ParticleSystem.setNamedBit("flags", "useLocalTime", particleSystem.useLocalTime)
            m3ParticleSystem.setNamedBit("flags", "simulateOnInit", particleSystem.simulateOnInit)
            m3ParticleSystem.setNamedBit("flags", "copy", particleSystem.copy)
            m3ParticleSystem.ar1 = self.createNullFloatAnimationReference(initValue=1.0, nullValue=0.0)

            materialIndices = []
            for materialIndex, material in enumerate(scene.m3_materials):
                if material.name == particleSystem.materialName:
                    materialIndices.append(materialIndex)
            
            if len(materialIndices) > 1:
                raise Exception("There are multiple materials with the same name")
            elif len(materialIndices) == 0:
                raise Exception("The material %s referenced by the particle system %s does not exist" % (m3ParticleSystem.materialName, m3ParticleSystem.name))
            m3ParticleSystem.matmIndex = materialIndices[0]

            model.particles.append(m3ParticleSystem)

    def toM3ColorComponent(self, blenderColorComponent):
        v = round(blenderColorComponent * 255)
        if v > 255:
            v = 255
        if v < 0:
            v = 0
        return v
    
    def toM3Color(self, blenderColor):
        color = m3.Color()
        color.red = self.toM3ColorComponent(blenderColor[0])
        color.green = self.toM3ColorComponent(blenderColor[1])
        color.blue = self.toM3ColorComponent(blenderColor[2])
        color.alpha = self.toM3ColorComponent(blenderColor[3])
        return color
        

    def createNullVector4As4uint8(self):
        vec = m3.Vector4As4uint8()
        vec.x = 0
        vec.y = 0
        vec.z = 0
        vec.w = 0
        return vec

    def createIdentityRestPosition(self):
        iref = m3.IREFV0()
        iref.matrix = self.createIdentityMatrix()
        return iref

    def createStaticBoneAtOrigin(self, name):
        m3Bone = m3.BONEV1()
        m3Bone.name = name
        m3Bone.flags = 0
        m3Bone.parent = -1
        m3Bone.location = self.createNullVector3AnimationReference(0.0, 0.0, 0.0)
        m3Bone.rotation = self.createNullQuaternionAnimationReference(x=0.0, y=0.0, z=0.0, w=1.0)
        m3Bone.scale = self.createNullVector3AnimationReference(1.0, 1.0, 1.0)
        m3Bone.ar1 = self.createNullUInt32AnimationReference(1)
        return m3Bone

    def initMaterials(self, model):
        standardMaterials = []
        materialReferences = model.materialReferences
        scene = self.scene
        
        for materialIndex, material in enumerate(scene.m3_materials):
            materialType = 1 # 1 = standard material
            materialReferences.append(self.createMaterialReference(materialIndex, materialType))
            standardMaterials.append(self.createMaterial(materialIndex, material))
        model.materialReferences = materialReferences 
        model.standardMaterials = standardMaterials
        
    def createMaterial(self, materialIndex, material):
        m3Material = m3.MAT_V15()
        m3Material.name = material.name
        m3Material.unknown0 = 13 # seems to stand for particle materials
        m3Material.setNamedBit("flags", "unfogged", material.unfogged)
        m3Material.setNamedBit("flags", "twoSided", material.twoSided)
        m3Material.setNamedBit("flags", "unshaded", material.unshaded)
        m3Material.setNamedBit("flags", "noShadowsCast", material.noShadowsCast)
        m3Material.setNamedBit("flags", "noHitTest", material.noHitTest)
        m3Material.setNamedBit("flags", "noShadowsReceived", material.noShadowsReceived)
        m3Material.setNamedBit("flags", "depthPrepass", material.depthPrepass)
        m3Material.setNamedBit("flags", "useTerrainHDR", material.useTerrainHDR)
        m3Material.setNamedBit("flags", "splatUVfix", material.splatUVfix)
        m3Material.setNamedBit("flags", "softBlending", material.softBlending)
        m3Material.setNamedBit("flags", "forParticles", material.forParticles)
        m3Material.blendMode = int(material.blendMode)
        m3Material.priority = material.priority
        m3Material.specularity = material.specularity
        m3Material.specMult = material.specMult
        m3Material.emisMult = material.emisMult
        
        layerIndex = 0
        for layer, layerFieldName in zip(material.layers, shared.materialLayerFieldNames):
            animPathPrefix = "m3_materials[%s].layers[%s]." % (materialIndex, layerIndex)
            m3Layer = self.createMaterialLayer(layer, animPathPrefix)
            setattr(m3Material, layerFieldName, [m3Layer])
            layerIndex += 1

        m3Material.layerBlendType = int(material.layerBlendType)
        m3Material.emisBlendType = int(material.emisBlendType)
        m3Material.specType = int(material.specType)
        m3Material.unknownAnimationRef1 = self.createNullUInt32AnimationReference(0)
        m3Material.unknownAnimationRef2 = self.createNullUInt32AnimationReference(0)
        return m3Material

    def createMaterialLayer(self, layer, animPathPrefix):
        m3Layer = m3.LAYRV22()
        m3Layer.imagePath = layer.imagePath
        transferer = BlenderToM3DataTransferer(exporter=self, m3Object=m3Layer, blenderObject=layer, animPathPrefix=animPathPrefix, actionOwnerName=self.scene.name, actionOwnerType=actionTypeScene)
        transferer.transferAnimatableColor("color")
        m3Layer.setNamedBit("flags", "textureWrapX", layer.textureWrapX)
        m3Layer.setNamedBit("flags", "textureWrapY", layer.textureWrapY)
        m3Layer.setNamedBit("flags", "colorEnabled", layer.colorEnabled)
        transferer.transferInt("uvChannel")
        m3Layer.setNamedBit("alphaFlags", "alphaAsTeamColor", layer.alphaAsTeamColor)
        m3Layer.setNamedBit("alphaFlags", "alphaOnly", layer.alphaOnly)
        m3Layer.setNamedBit("alphaFlags", "alphaBasedShading", layer.alphaBasedShading)
        transferer.transferAnimatableFloat("brightMult")
        transferer.transferAnimatableFloat("brightMult2")
        m3Layer.unknown6 = self.createNullUInt32AnimationReference(0)
        m3Layer.unknown7 = self.createNullVector2AnimationReference(0.0, 0.0)
        m3Layer.unknown8 = self.createNullUInt16AnimationReference(0)
        m3Layer.uvOffset = self.createNullVector2AnimationReference(0.0, 0.0)
        m3Layer.uvAngle = self.createNullVector3AnimationReference(0.0, 0.0, 0.0)
        m3Layer.uvTiling = self.createNullVector2AnimationReference(1.0, 1.0)
        m3Layer.uvTiling = self.createNullVector2AnimationReference(1.0, 1.0)
        m3Layer.unknown9 = self.createNullUInt32AnimationReference(0)
        m3Layer.unknown10 = self.createNullFloatAnimationReference(1.0)
        transferer.transferAnimatableFloat("brightness")
        return m3Layer

    def createNullVector2AnimationReference(self, x, y):
        animRef = m3.Vector2AnimationReference()
        animRef.header = self.createNullAnimHeader()
        animRef.initValue = self.createVector2(x, y)
        animRef.nullValue = self.createVector2(x, y)
        return animRef
        
    def createNullVector3AnimationReference(self, x, y, z):
        animRef = m3.Vector3AnimationReference()
        animRef.header = self.createNullAnimHeader()
        animRef.initValue = self.createVector3(x, y, z)
        animRef.nullValue = self.createVector3(x, y, z)
        return animRef
    
    def createNullQuaternionAnimationReference(self, x=0.0, y=0.0, z=0.0, w=1.0):
        animRef = m3.QuaternionAnimationReference()
        animRef.header = self.createNullAnimHeader()
        animRef.initValue = self.createQuaternion(x=x, y=y, z=z, w=w)
        animRef.nullValue = self.createQuaternion(x=x, y=y, z=z, w=w)
        return animRef
        
    def createNullUInt16AnimationReference(self, value):
        animRef = m3.UInt16AnimationReference()
        animRef.header = self.createNullAnimHeader()
        animRef.initValue = value
        animRef.nullValue = value
        return animRef
        
    def createNullUInt32AnimationReference(self, value):
        animRef = m3.UInt32AnimationReference()
        animRef.header = self.createNullAnimHeader()
        animRef.initValue = value
        animRef.nullValue = value
        return animRef
        
    def createNullFloatAnimationReference(self, initValue, nullValue=None):
        if nullValue == None:
            nullValue = initValue
        animRef = m3.FloatAnimationReference()
        animRef.header = self.createNullAnimHeader()
        animRef.initValue = initValue
        animRef.nullValue = nullValue
        return animRef
    
    def createNullAnimHeader(self):
        animRefHeader = m3.AnimationReferenceHeader()
        animRefHeader.flags = 0
        animRefHeader.animFlags = 0
        animRefHeader.animId = self.createUniqueAnimId()
        return animRefHeader
        
    def createUniqueAnimId(self):
        self.generatedAnimIdCounter += 1 # increase first since we don't want to use 0 as animation id
        return self.generatedAnimIdCounter
    
    def createMaterialReference(self, materialIndex, materialType):
        materialReference = m3.MATMV0()
        materialReference.matType = materialType
        materialReference.matIndex = materialIndex
        return materialReference

    def createEmptyDivision(self):
        division = m3.DIV_V2()
        division.faces = []
        division.regions = []
        division.bat = []
        division.msec = [self.createEmptyMSec()]
        return division
    
    def createEmptyMSec(self):
        msec = m3.MSECV1()
        msec.boundingsAnimation = self.createDummyBoundingsAnimation()
        return msec
    
    def createDummyBoundingsAnimation(self):
        boundingsAnimRef = m3.BNDSV0AnimationReference()
        animHeader = m3.AnimationReferenceHeader()
        animHeader.flags = 0x0
        animHeader.animFlags = 0x0
        animHeader.animId = 0x1f9bd2 # boudings seem to have always this id
        #TODO make sure the animID is unique
        boundingsAnimRef.header = animHeader
        boundingsAnimRef.initValue = self.createEmptyBoundings()
        boundingsAnimRef.nullValue = self.createEmptyBoundings()
        return boundingsAnimRef
    
    def createEmptyBoundings(self):
        boundings = m3.BNDSV0()
        boundings.min = self.createVector3(0.0,0.0,0.0)
        boundings.max = self.createVector3(0.0,0.0,0.0)
        boundings.radius = 0.0
        return boundings
        
    def createAlmostEmptyBoundingsWithRadius(self, r):
        boundings = m3.BNDSV0()
        boundings.min = self.createVector3(0.0,0.0,0.0)
        epsilon = 9.5367431640625e-07
        boundings.max = self.createVector3(epsilon, epsilon, epsilon)
        boundings.radius = r
        return boundings

    def createVector4(self, x, y, z, w):
        v = m3.Vector4()
        v.x = x
        v.y = y
        v.z = z
        v.w = w
        return v
    
    def createQuaternion(self, x, y, z, w):
        q = m3.QUATV0()
        q.x = x
        q.y = y
        q.z = z
        q.w = w
        return q
        
    def createVector3(self, x, y, z):
        v = m3.VEC3V0()
        v.x = x
        v.y = y
        v.z = z
        return v
    
    def createVector2(self, x, y):
        v = m3.VEC2V0()
        v.x = x
        v.y = y
        return v
        
    def createVector3FromBlenderVector(self, blenderVector):
        return self.createVector3(blenderVector.x, blenderVector.y, blenderVector.z)
    
    def createIdentityMatrix(self):
        matrix = m3.Matrix44()
        matrix.x = self.createVector4(1.0, 0.0, 0.0, 0.0)
        matrix.y = self.createVector4(0.0, 1.0, 0.0, 0.0)
        matrix.z = self.createVector4(0.0, 0.0, 1.0, 0.0)
        matrix.w = self.createVector4(0.0, 0.0, 0.0, 1.0)
        return matrix
        

class BlenderToM3DataTransferer:
    
    def __init__(self, exporter, m3Object, blenderObject, animPathPrefix,  actionOwnerName, actionOwnerType):
        self.exporter = exporter
        self.m3Object = m3Object
        self.blenderObject = blenderObject
        self.animPathPrefix = animPathPrefix
        self.actionOwnerName = actionOwnerName
        self.actionOwnerType = actionOwnerType
        
        self.animationActionTuples = []
        
        scene = self.exporter.scene
        for animation in scene.m3_animations:
            for assignedAction in animation.assignedActions:
                if actionOwnerName == assignedAction.targetName:
                    actionName = assignedAction.actionName
                    action = bpy.data.actions.get(actionName)
                    if action == None:
                        print("Warning: The action %s was referenced by name but does no longer exist" % assignedAction.actionName)
                    else:
                        if action.id_root == actionOwnerType:
                            self.animationActionTuples.append((animation, action))
        
    def transferAnimatableColor(self, fieldName):
        animRef = m3.ColorAnimationReference()
        animRef.header = self.exporter.createNullAnimHeader()
        m3CurrentColor =  self.exporter.toM3Color(getattr(self.blenderObject, fieldName))
        animRef.initValue = m3CurrentColor
        animRef.nullValue = m3CurrentColor
        setattr(self.m3Object, fieldName, animRef)
        #TODO export the animations

    def transferAnimatableFloat(self, fieldName):
        animRef = m3.FloatAnimationReference()
        animRef.header = self.exporter.createNullAnimHeader()
        currentValue =  getattr(self.blenderObject, fieldName)
        animRef.initValue = currentValue
        animRef.nullValue = currentValue
        
        animId = animRef.header.animId
        animPath = self.animPathPrefix + fieldName
        
        for animation, action in self.animationActionTuples:
            frames = self.getAllFramesOf(animation)
            timeValuesInMS = self.allFramesToMSValues(frames)
            values = self.getNoneOrValuesFor(action, animPath, 0, frames)
            
            if values != None:
                m3AnimBlock = m3.SDR3V0()
                m3AnimBlock.frames = timeValuesInMS
                m3AnimBlock.flags = 0
                m3AnimBlock.fend = self.exporter.frameToMS(animation.endFrame)
                m3AnimBlock.keys = values
                
                animIdToAnimDataMap = self.exporter.nameToAnimIdToAnimDataMap[animation.name]
                animIdToAnimDataMap[animId] = m3AnimBlock
                animRef.header.flags = 1
                animRef.header.animFlags = shared.animFlagsForAnimatedProperty
        #TODO Optimization: Remove keyframes that can be calculated by interpolation
        setattr(self.m3Object, fieldName, animRef)
    
    def transferAnimatableUInt16(self, fieldName):
        animRef = m3.UInt16AnimationReference()
        animRef.header = self.exporter.createNullAnimHeader()
        currentValue =  getattr(self.blenderObject, fieldName)
        animRef.initValue = currentValue
        animRef.nullValue = currentValue
        setattr(self.m3Object, fieldName, animRef)
        #TODO export the animations

    
    def transferAnimatableUInt32(self, fieldName):
        animRef = m3.UInt32AnimationReference()
        animRef.header = self.exporter.createNullAnimHeader()
        currentValue =  getattr(self.blenderObject, fieldName)
        animRef.initValue = currentValue
        animRef.nullValue = currentValue
        setattr(self.m3Object, fieldName, animRef)
        #TODO export the animations

    def transferAnimatableVector3(self, fieldName):
        animRef = m3.Vector3AnimationReference()
        animRef.header = self.exporter.createNullAnimHeader()
        currentBVector =  getattr(self.blenderObject, fieldName)
        animRef.initValue = self.exporter.createVector3FromBlenderVector(currentBVector)
        animRef.nullValue = self.exporter.createVector3FromBlenderVector(currentBVector)
        setattr(self.m3Object, fieldName, animRef)
        
        
        animId = animRef.header.animId
        animPath = self.animPathPrefix + fieldName
        
        for animation, action in self.animationActionTuples:
            frames = self.getAllFramesOf(animation)
            timeValuesInMS = self.allFramesToMSValues(frames)
            xValues = self.getNoneOrValuesFor(action, animPath, 0, frames)
            yValues = self.getNoneOrValuesFor(action, animPath, 1, frames)
            zValues = self.getNoneOrValuesFor(action, animPath, 2, frames)
            if (xValues != None) or (yValues != None) or (zValues != None):
                if xValues == None:
                    xValues = len(timeValuesInMS) * [currentBVector.x]
                if yValues == None:
                    yValues = len(timeValuesInMS) * [currentBVector.y]
                if zValues == None:
                    zValues = len(timeValuesInMS) * [currentBVector.z]
                vectors = []
                for (x,y,z) in zip(xValues, yValues, zValues):
                    vec = self.exporter.createVector3(x,y,z)
                    vectors.append(vec)
                
                m3AnimBlock = m3.SD3VV0()
                m3AnimBlock.frames = timeValuesInMS
                m3AnimBlock.flags = 0
                m3AnimBlock.fend = self.exporter.frameToMS(animation.endFrame)
                m3AnimBlock.keys = vectors
                
                animIdToAnimDataMap = self.exporter.nameToAnimIdToAnimDataMap[animation.name]
                animIdToAnimDataMap[animId] = m3AnimBlock
                animRef.header.flags = 1
                animRef.header.animFlags = shared.animFlagsForAnimatedProperty
        #TODO Optimization: Remove keyframes that can be calculated by interpolation
        
    def transferInt(self, fieldName):
        value = getattr(self.blenderObject, fieldName)
        setattr(self.m3Object, fieldName , value)
        
    def transferBoolToInt(self, fieldName):
        boolValue = getattr(self.blenderObject, fieldName)
        if boolValue:
            intValue = 1
        else:
            intValue = 0
        setattr(self.m3Object, fieldName , intValue)

    def transferFloat(self, fieldName):
        value = getattr(self.blenderObject, fieldName)
        setattr(self.m3Object, fieldName , value)
        
    def transferEnum(self, fieldName):
        value = getattr(self.blenderObject, fieldName)
        setattr(self.m3Object, fieldName , int(value))
        
    def getAllFramesOf(self, animation):
        #TODO Does the end frame need to be included?
        return range(animation.startFrame, animation.endFrame)
        
    def allFramesToMSValues(self, frames):
        timeValues = []
        for frame in frames:
            timeInMS = self.exporter.frameToMS(frame)
            timeValues.append(timeInMS)
        return timeValues
    
    def getNoneOrValuesFor(self, action, animPath, curveArrayIndex, frames):
        values = []
        curve = self.findFCurveWithPathAndIndex(action, animPath, curveArrayIndex)
        if curve == None:
            return None
        for frame in frames:
            values.append(curve.evaluate(frame))
        return values
            
    def findFCurveWithPathAndIndex(self, action, animPath, curveArrayIndex):
        for curve in action.fcurves:
            if (curve.data_path == animPath) and (curve.array_index == curveArrayIndex):
                return curve
        return None
        
def exportParticleSystems(scene, filename):
    exporter = Exporter()
    shared.setAnimationWithIndexToCurrentData(scene, scene.m3_animation_index)
    exporter.exportParticleSystems(scene, filename)
