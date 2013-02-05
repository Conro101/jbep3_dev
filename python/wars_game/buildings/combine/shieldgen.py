import random

from srcbase import SOLID_OBB, FSOLID_NOT_SOLID, RegisterTickMethod, UnregisterTickMethod, DMG_SHOCK, Color
from vmath import (VectorNormalize, VectorAngles, AngleVectors, QAngle, Vector, VectorYawRotate, DotProduct, 
                  matrix3x4_t, AngleMatrix, TransformAABB)
            
from core.buildings import WarsBuildingInfo, UnitBaseBuilding as BaseClass

from fields import GenericField, IntegerField, FloatField
from entities import entity
if isserver:
    from entities import gEntList, CTriggerMultiple as BaseClassShield, CreateEntityByName, DispatchSpawn, CTakeDamageInfo, DoSpark, SpawnBlood, D_LI, FL_EDICT_ALWAYS
    from particles import PrecacheParticleSystem, DispatchParticleEffect, ParticleAttachment_t
    from utils import UTIL_SetSize, UTIL_Remove
else:
    from vgui import surface, scheme
    from vgui.entitybar import UnitBarScreen
    from entities import DataUpdateType_t, CLIENT_THINK_ALWAYS, C_BaseEntity as BaseClassShield
    from particles import ParticleAttachment_t
    from te import FXCube
    from utils import GetVectorInScreenSpace
    
FORCEFIELD_PARTICLEEFFECT = 'st_elmos_fire'

if isclient:
    class UnitEnergyBarScreen(UnitBarScreen):
        """ Draws the unit health bar. """
        def __init__(self, unit):
            super(UnitEnergyBarScreen, self).__init__(unit,
                Color(0, 0, 255, 200), Color(40, 40, 40, 250), Color(150, 150, 150, 200), 
                offsety=4.0)
            
        def Draw(self):
            panel = self.GetPanel()
            if self.unit.shield:
                shield = self.unit.shield
                panel.weight = shield.energy/shield.energymax
            else:
                panel.weight = 0.0
                    
            super(UnitEnergyBarScreen, self).Draw()

# Shield
@entity('comb_shield', networked=True)
class CombineShield(BaseClassShield):
    if isserver:
        def Spawn(self):
            self.AddSpawnFlags( 0x02 )
            
            self.Precache()
            
            self.touchinglist = []
            
            super(CombineShield, self).Spawn()
            
            self.SetSolid(SOLID_OBB)

            self.SetThink(self.ForceThink, gpGlobals.curtime, 'ForceThink')
            
        def UpdateOnRemove(self):
            super(CombineShield, self).UpdateOnRemove()
            
            self.gen1.RemoveLink(self)
            self.gen2.RemoveLink(self)
        
        def UpdateTransmitState(self):
            return self.SetTransmitState( FL_EDICT_ALWAYS )
        
        # TODO: Should put this in the unit ai. The movement code will try to zero out the velocity.
        def StartTouch(self, entity):
            #super(CombineShield, self).StartTouch(entity)
            if not entity.IsUnit() or entity.isbuilding or entity.IRelationType(self) == D_LI: 
                return
            
            dir = Vector()
            AngleVectors(self.GetAbsAngles(), dir)
            VectorYawRotate(dir, 90.0, dir)

            # Use steporigin since the abs origin might already be passed the forcefield
            dirent = entity.GetStepOrigin() - self.GetAbsOrigin()
            VectorNormalize(dirent)
            dot = DotProduct(dir, dirent)

            if dot < 0.0:
                VectorYawRotate(dir, 180.0, dir)
            
            self.touchinglist.append( (entity, dir) )
            self.PushEntity(entity, dir)
            
        def EndTouch(self, entity):
            for i in self.touchinglist:
                if i[0] == entity:
                    self.touchinglist.remove(i)
                    break
                    
        def PushEntity(self, entity, dir):
            if hasattr(entity, 'DispatchEvent'):
                entity.DispatchEvent('OnForceField', self)
                
            speed = 750.0
            entity.SetGroundEntity(None)
           
            entity.SetAbsVelocity(dir * speed + Vector(0, 0, 250.0))
            
            damage = 1.0
            info = CTakeDamageInfo(self, self, damage, DMG_SHOCK)
            entity.TakeDamage(info)
            
            SpawnBlood(entity.GetAbsOrigin(), Vector(0,0,1), entity.BloodColor(), damage)
            dir = Vector()
            dir.Random(-1.0, 1.0)
            DoSpark(entity, entity.GetAbsOrigin(), 100, 100, True, dir)
            
            self.energy -= self.drainperentity*self.pushfrequency

        def ForceThink(self):
            self.energy = min(self.energymax, self.energy + self.pushfrequency*self.energypersecond)
            for i in self.touchinglist:
                self.PushEntity(i[0], i[1])
            if self.energy < 0:
                self.OutOfEnergy()
            self.SetNextThink(gpGlobals.curtime + self.pushfrequency, 'ForceThink')
            
        def OutOfEnergy(self):
            self.gen1.AddDelayedLink(self.gen2, 5.0)
            self.Remove()
            
        gen1 = None
        gen2 = None
    else:
        def OnDataChanged(self, type):
            super(CombineShield, self).OnDataChanged(type)
            
            if type == DataUpdateType_t.DATA_UPDATE_CREATED:
                mins = self.WorldAlignMins()
                maxs = self.WorldAlignMaxs()
                mins.y = -2.0
                maxs.y = 2.0
                self.mesh = FXCube("effects/com_shield003b", Vector(1.0, 1.0, 1.0), mins, maxs, self.GetAbsOrigin(), self.GetAbsAngles())
            
        def UpdateOnRemove(self):
            super(CombineShield, self).Spawn()
            if self.mesh:
                self.mesh.Destroy()
                self.mesh = None
            
        mesh = None
    
    pushfrequency = FloatField(value=0.10)
    energymax = IntegerField(value=100, networked=True)
    energy = IntegerField(value=energymax.default, networked=True)
    energypersecond = IntegerField(value=1)
    drainperentity = IntegerField(value=15)
    
    # Particle version
    # class CombineShieldLink(object):
        # def __init__(self, gen1, gen2):
            # super(CombineShieldLink, self).__init__()
            
            # self.gen1 = gen1
            # self.gen2 = gen2
            # self.i = 0
            # self.effect = None

            # self.minz = gen1.WorldAlignMins().z
            # self.maxz = gen1.WorldAlignMaxs().z
            
            # RegisterTickMethod(self.Update, 0.1)
            
        # def Shutdown(self):
            # UnregisterTickMethod(self.Update)
            # self.gen1.RemoveLink(self)
            # self.gen2.RemoveLink(self)
            
        # def Update(self):
            # effect = self.gen1.ParticleProp().Create( FORCEFIELD_PARTICLEEFFECT, ParticleAttachment_t.PATTACH_ABSORIGIN )
            # self.effect = effect
            # if effect:
                # if self.i == 0:
                    # origin1 = self.gen1.GetAbsOrigin()
                    # origin1.z += random.uniform(self.minz, self.maxz)
                    # origin2 = self.gen2.GetAbsOrigin()
                    # origin2.z += random.uniform(self.minz, self.maxz)
                # else:
                    # origin1 = self.gen2.GetAbsOrigin()
                    # origin1.z += random.uniform(self.minz, self.maxz)
                    # origin2 = self.gen1.GetAbsOrigin()
                    # origin2.z += random.uniform(self.minz, self.maxz)
                # self.i = (self.i + 1) % 2
                
                # effect.SetControlPoint(0, origin1)
                # effect.SetControlPoint(1, origin2)
                
                # dir = (origin2 - origin1)
                # VectorNormalize(dir)
                # effect.SetControlPointForwardVector(0, dir)
                # effect.SetControlPointForwardVector(1, -dir)
                    
# Forcefield Generator. Between nearby generators a forcefield is created.
@entity('build_comb_shieldgen', networked=True)
class CombineShieldGenerator(BaseClass):
    autoconstruct = False
    
    def __init__(self):
        super(CombineShieldGenerator, self).__init__()

        self.links = []
        self.delayedlinks = []

    def RemoveLink(self, link):
        if link == self.shield:
            self.shield = None
        self.links.remove(link)
        
    if isserver:
        def UpdateOnRemove(self):
            super(CombineShieldGenerator, self).UpdateOnRemove()
            
            self.DestroyAllLinks()
            
        def Precache(self):
            super(CombineShieldGenerator, self).Precache()
            self.PrecacheScriptSound('DoSpark')
            #PrecacheParticleSystem(FORCEFIELD_PARTICLEEFFECT)
            
        def OnConstructed(self):
            super(CombineShieldGenerator, self).OnConstructed()
            
            # Find nearest forcefield generator
            bestgen = None
            gen = gEntList.FindEntityByClassnameWithin(None, 'build_comb_shieldgen', self.GetAbsOrigin(), self.maxgenrange)
            while gen:
                if gen == self:
                    gen = gEntList.FindEntityByClassnameWithin(gen, 'build_comb_shieldgen', self.GetAbsOrigin(), self.maxgenrange)
                    continue
                dist = (self.GetAbsOrigin() - gen.GetAbsOrigin()).Length2D()
                if not bestgen:
                    bestgen = gen
                    bestdist = dist
                else:
                    if dist < bestdist:
                        bestgen = gen
                        bestdist = dist
                gen = gEntList.FindEntityByClassnameWithin(gen, 'build_comb_shieldgen', self.GetAbsOrigin(), self.maxgenrange)
                
            if bestgen and not self.GetLink(bestgen):
                self.CreateLink(bestgen)
            
        def GetLink(self, othergen):
            for link in self.links:
                if link.gen1 == othergen or link.gen2 == othergen:
                    return link
            return None
            
        def CreateLink(self, othergen):
            if othergen == self:
                return
                
            dir = othergen.GetAbsOrigin() - self.GetAbsOrigin()
            dir.z = 0.0
            dist = VectorNormalize(dir)
            angle = QAngle()
            VectorAngles(dir, angle)
            
            mins = -Vector((dist/2.0)-16.0, 48.0, -self.WorldAlignMins().z)
            maxs = Vector((dist/2.0)-16.0, 48.0, self.WorldAlignMaxs().z-32.0)
            
            origin = self.GetAbsOrigin() + dir * (dist/2.0)
            origin.z = self.GetAbsOrigin().z + self.WorldAlignMins().z + (maxs.z - mins.z)/2.0

            # Create the pusher
            link = CreateEntityByName('comb_shield')
            link.SetAbsOrigin(origin)
            link.SetOwnerNumber(self.GetOwnerNumber())
            DispatchSpawn(link)
            link.Activate()
            UTIL_SetSize(link, mins, maxs)
            link.SetAbsAngles(angle)
            link.Enable()
            
            link.gen1 = self.GetHandle()
            link.gen2 = othergen
            
            self.LinkToShield(link)

            othergen.LinkToShield(link)
            
        def LinkToShield(self, shield):
            self.links.append(shield)
            self.shield = shield
            
        def DestroyLink(self, link):
            UTIL_Remove(link)
            
        def DestroyAllLinks(self):
            links = self.links[:]
            for link in links:
                self.DestroyLink(link)
        
        def AddDelayedLink(self, othergen, delay):
            self.delayedlinks.append( (othergen, gpGlobals.curtime + delay ) )
            self.SetThink(self.DelayedLinkThink, 0.1, 'DelayedLinkThink')
        
        def DelayedLinkThink(self):
            if not self.delayedlinks:
                return
            delayedlinks = list(self.delayedlinks)
            for dl in delayedlinks:
                if dl[1] < gpGlobals.curtime:
                    if dl[0] and not self.GetLink(dl[0]):
                        self.CreateLink(dl[0])
                    self.delayedlinks.remove(dl)
                    
            self.SetThink(self.DelayedLinkThink, 0.1, 'DelayedLinkThink')
            
    else:
        def ShowBars(self):
            if self.barsvisible:
                return
                
            self.energybarscreen = UnitEnergyBarScreen(self)
                
            super(CombineShieldGenerator, self).ShowBars()
            
        def HideBars(self):
            if not self.barsvisible:
                return
                
            self.energybarscreen.Shutdown()
            self.energybarscreen = None
            
            super(CombineShieldGenerator, self).HideBars()

    maxgenrange = FloatField(value=720.0)
    shield = GenericField(value=None, networked=True)

class CombineMedicStationInfo(WarsBuildingInfo):
    name        = 'overrun_build_comb_shieldgen'
    displayname = '#BuildCombShieldGen_Name'
    description = '#BuildCombShieldGen_Description'
    cls_name    = 'build_comb_shieldgen'
    image_name  = 'vgui/abilities/shield.vmt'
    image_dis_name = 'vgui/abilities/shield_dis.vmt'
    modelname = 'models/props_combine/combine_generator01.mdl'
    health = 300
    buildtime = 25.0
    placemaxrange = 96.0
    costs = [[('kills', 3)], [('requisition', 3)]]
    techrequirements = ['or_tier3_research']
    abilities   = {
        0 : 'genconnect',
        1 : 'gendestroylinks',
        8 : 'cancel',
    } 