from srcbase import (Color, SOLID_NONE, SOLID_VPHYSICS, FSOLID_TRIGGER, DAMAGE_EVENTS_ONLY, DAMAGE_NO, 
                    kRenderTransAdd, kRenderFxNone, MASK_SHOT, CONTENTS_GRATE,
                    COLLISION_GROUP_INTERACTIVE, COLLISION_GROUP_DEBRIS, COLLISION_GROUP_NONE)
from vmath import vec3_origin, Vector, QAngle, VectorNormalize
import math
import random
from entities import entity, networked, Activity, FOWFLAG_UNITS_MASK
from gameinterface import ConVarRef
from core.units import UnitInfo, UnitBase as BaseClass, CreateUnitNoSpawn
from core.abilities import AbilityUpgrade
from core.abilities.placeobject import AbilityPlaceObjectShared

if isserver:
    from gameinterface import CReliableBroadcastRecipientFilter, CPVSFilter
    from entities import CSoundEnt, SOUND_DANGER, CSprite, gEntList, DispatchSpawn
    from sound import CSoundEnvelopeController, PITCH_NORM
    from core.units import UnitCombatSense
    from utils import (UTIL_Remove, trace_t, UTIL_TraceLine, ExplosionCreate,
                      UTIL_FindPosition, FindPositionInfo)
    from physics import PhysSetGameFlags, PhysClearGameFlags, FVPHYSICS_CONSTRAINT_STATIC, FVPHYSICS_PLAYER_HELD, CALLBACK_GLOBAL_TOUCH_STATIC

sv_gravity = ConVarRef('sv_gravity')

AngularImpulse = Vector

@networked
@entity('bounce_bomb')
@entity('combine_bouncemine')
@entity('combine_mine')
class BounceBomb(BaseClass):
    # FIXME: Setting the pose parameters on the client ain't working.
    # if isclient:
        # def OnNewModel(self):
            # super(BounceBomb, self).OnNewModel()

            # self.hookn = self.LookupPoseParameter( "blendnorth" )
            # self.hooke = self.LookupPoseParameter( "blendeast" )
            # self.hooks = self.LookupPoseParameter( "blendsouth" )
            # self.allhooks = self.LookupPoseParameter( "blendstates" )
            
            # self.targetstate = 0
            
            # #self.SetSequence( self.SelectWeightedSequence( Activity.ACT_IDLE ) )
    
        # def ReceiveEvent(self, event, data):
            # if event is self.EVENT_HOOKOPEN:
                # print 'Event open'
                # self.targetstate = 64.0#self.BOUNCEBOMB_HOOK_RANGE
                # #self.SetPoseParameter( self.allhooks, self.BOUNCEBOMB_HOOK_RANGE )
            # elif event is self.EVENT_HOOKCLOSE:
                # print 'event close'
                # self.targetstate = 0.0
                # #self.SetPoseParameter( self.allhooks, 0 )
            # elif event is self.EVENT_CAPTIVEON:
                # self.captiveon = True
            # elif event is self.EVENT_CAPTIVEOFF:
                # self.captiveon = False
                
        # def UpdateClientSideAnimation(self):
            # """ Update the client side animations + state """
            # #super(BounceBomb, self).UpdateClientSideAnimation()
            
            # blendstates = self.GetPoseParameter(self.allhooks)
            # modelptr = self.GetModelPtr()
            # #print 'blendstates: %f, targetstate: %f' % (blendstates, self.targetstate)
            # #if self.captiveon:
            # #    phase = math.abs( math.sin( gpGlobals.curtime * 4.0 ) )
            # #    phase *= self.BOUNCEBOMB_HOOK_RANGE
            # #    self.SetPoseParameter( self.allhooks, phase )  

            # if blendstates < self.targetstate:
                # newblendstates = min(self.targetstate, blendstates + 10.0)
                # blendstates = self.SetPoseParameter(modelptr, self.allhooks, newblendstates) 
                # blendstates = self.GetPoseParameter(self.allhooks)
            # elif blendstates > self.targetstate:
                # newblendstates = max(self.targetstate, blendstates - 10.0)
                # blendstates = self.SetPoseParameter(modelptr, self.allhooks, newblendstates) 
                # blendstates = self.GetPoseParameter(self.allhooks)

    # captiveon = False
    # EVENT_HOOKOPEN = 0
    # EVENT_HOOKCLOSE = 1
    # EVENT_CAPTIVEON = 2
    # EVENT_CAPTIVEOFF = 3
    
    if isserver:
        def __init__(self):
            super(BounceBomb, self).__init__()
            
            self.lastspritecolor = Color()
            
            self.SetCanBeSeen(False)

            self.UseClientSideAnimation()
                
        def CreateVPhysics(self):
            self.VPhysicsInitNormal( SOLID_VPHYSICS, 0, False )
            return True
        
        def Precache(self):
            self.PrecacheModel("models/props_combine/combine_mine01.mdl")

            self.PrecacheScriptSound( "NPC_CombineMine.Hop" )
            self.PrecacheScriptSound( "NPC_CombineMine.FlipOver" )
            self.PrecacheScriptSound( "NPC_CombineMine.TurnOn" )
            self.PrecacheScriptSound( "NPC_CombineMine.TurnOff" )
            self.PrecacheScriptSound( "NPC_CombineMine.OpenHooks" )
            self.PrecacheScriptSound( "NPC_CombineMine.CloseHooks" )

            self.PrecacheScriptSound( "NPC_CombineMine.ActiveLoop" )

            self.PrecacheModel( "sprites/glow01.vmt" )

        def Spawn(self):
            super(BounceBomb, self).Spawn()

            self.Wake( False )

            self.SetModel("models/props_combine/combine_mine01.mdl")

            self.SetSolid( SOLID_VPHYSICS )
            self.SetGravity(2.0) # Fall down a bit more quickly

            self.sprite = None
            self.takedamage = DAMAGE_EVENTS_ONLY
            
            self.senses = UnitCombatSense(self)

            # Find my feet!
            self.hookn = self.LookupPoseParameter( "blendnorth" )
            self.hooke = self.LookupPoseParameter( "blendeast" )
            self.hooks = self.LookupPoseParameter( "blendsouth" )
            self.allhooks = self.LookupPoseParameter( "blendstates" )
            self.hookpositions = 0

            self.heatlh = 100

            self.bounce = True

            self.SetSequence( self.SelectWeightedSequence( Activity.ACT_IDLE ) )

            self.OpenHooks( True )

            self.heldbyphysgun = False

            self.flipattempts = 0

            if not self.GetParent():
                # Create vphysics now if I'm not being carried.
                self.CreateVPhysics()
                
            self.timegrabbed = float('inf') #FLT_MAX

            if self.disarmed:
                self.SetMineState( self.MINE_STATE_DORMANT )
            else:
                self.SetMineState( self.MINE_STATE_DEPLOY )

            # # default to a different skin for cavern turrets (unless explicitly overridden)
            # if ( self.modification == MINE_MODIFICATION_CAVERN )
            
                # # look for self value in the first datamap
                # # loop through the data description list, restoring each data desc block
                # datamap_t *dmap = GetDataDescMap()

                # bool bFoundSkin = False
                # # search through all the readable fields in the data description, looking for a match
                # for ( int i = 0 i < dmap.dataNumFields ++i )
                
                    # if ( dmap.dataDesc[i].flags & (FTYPEDESC_OUTPUT | FTYPEDESC_KEY) )
                    
                        # if ( !Q_stricmp(dmap.dataDesc[i].externalName, "Skin") )
                        
                            # bFoundSkin = True 
                            # break
                        
                    
                

                # if (!bFoundSkin)
                
                    # # select a random skin for the mine. Actually, we'll cycle through the available skins 
                    # # using a static variable to provide better distribution. The static isn't saved but
                    # # really it's only cosmetic.
                    # static unsigned int nextSkin = MINE_CITIZEN_SKIN_MIN
                    # m_nSkin = nextSkin
                    # # increment the skin for next time
                    # nextSkin = (nextSkin >= MINE_CITIZEN_SKIN_MAX) ? MINE_CITIZEN_SKIN_MIN : nextSkin + 1

                # # pretend like the player set me down.
                # self.placedbyplayer = True
            
        # def OnRestore()
        
            # BaseClass::OnRestore()
            # if ( gpGlobals.eLoadType == MapLoad_Transition and !self.sprite and self.lastspritecolor.GetRawColor() != 0 )
            
                # UpdateLight( True, self.lastspritecolor.r(), self.lastspritecolor.g(), self.lastspritecolor.b(), self.lastspritecolor.a() )
            

            # if( VPhysicsGetObject() )
            
                # VPhysicsGetObject().Wake()

        # def DrawDebugTextOverlays(void) 
        
            # int text_offset = BaseClass::DrawDebugTextOverlays()
            # if (m_debugOverlays & OVERLAY_TEXT_BIT) 
            
                # char tempstr[512]
                # Q_snprintf(tempstr,sizeof(tempstr), pszMineStateNames[self.minestate] )
                # EntityText(text_offset,tempstr,0)
                # text_offset++
            
            # return text_offset
            
        def UpdateOnRemove(self):
            # ALWAYS CHAIN BACK!
            super(BounceBomb, self).UpdateOnRemove()

            if self.senses:
                del self.senses
                
        def Event_Killed(self, info):
            super(BounceBomb, self).Event_Killed(info)
            
            UTIL_Remove(self)
                
        def SetMineState(self, iState):
            if iState is self.minestate:
                return
                
            #if self.minestate is self.MINE_STATE_CAPTIVE:
                #filter = CPVSFilter(self.GetAbsOrigin())
                #self.SendEvent(filter, self.EVENT_CAPTIVEOFF)
           
            self.minestate = iState

            if iState is self.MINE_STATE_DORMANT:
                controller = CSoundEnvelopeController.GetController()
                controller.SoundChangeVolume( self.warnsound, 0.0, 0.1 )
                self.UpdateLight( False, 0, 0, 0, 0 )
                self.SetThink( None )
                
            elif iState is self.MINE_STATE_CAPTIVE:
                controller = CSoundEnvelopeController.GetController()
                controller.SoundChangeVolume( self.warnsound, 0.0, 0.2 )

                # Unhook
                flags = self.VPhysicsGetObject().GetCallbackFlags()
                self.VPhysicsGetObject().SetCallbackFlags( flags | CALLBACK_GLOBAL_TOUCH_STATIC )
                self.OpenHooks()
                physenv.DestroyConstraint( self.constraint )
                self.constraint = None

                self.UpdateLight( True, 0, 0, 255, 190 )
                self.SetThink( self.CaptiveThink )
                self.SetNextThink( gpGlobals.curtime + 0.1 )
                self.SetTouch( None )
                
                #filter = CPVSFilter(self.GetAbsOrigin())
                #self.SendEvent(filter, self.EVENT_CAPTIVEON)
                    
            elif iState is self.MINE_STATE_DEPLOY:
                self.OpenHooks( True )
                self.UpdateLight( True, 0, 0, 255, 190 )
                self.SetThink( self.SettleThink )
                self.SetTouch( None )
                self.SetNextThink( gpGlobals.curtime + 0.1 )

            elif iState is self.MINE_STATE_ARMED:
                self.UpdateLight( False, 0, 0, 0, 0 )
                self.SetThink( self.SearchThink )
                self.SetNextThink( gpGlobals.curtime + 0.1 )

            elif iState is self.MINE_STATE_TRIGGERED:
                self.OpenHooks()

                if self.constraint:
                    physenv.DestroyConstraint( self.constraint )
                    self.constraint = None

                # Scare NPC's
                #CSoundEnt.InsertSound( SOUND_DANGER, self.GetAbsOrigin(), 300, 1.0, self )

                controller = CSoundEnvelopeController.GetController()
                controller.SoundChangeVolume( self.warnsound, 0.0, 0.2 )

                self.SetTouch( self.ExplodeTouch )
                flags = self.VPhysicsGetObject().GetCallbackFlags()
                self.VPhysicsGetObject().SetCallbackFlags( flags | CALLBACK_GLOBAL_TOUCH_STATIC )

                vecNudge = Vector()

                vecNudge.x = random.uniform( -1, 1 )
                vecNudge.y = random.uniform( -1, 1 )
                vecNudge.z = 1.5
                vecNudge *= 350

                self.VPhysicsGetObject().Wake()
                self.VPhysicsGetObject().ApplyForceCenter( vecNudge )

                x = 10 + random.uniform( 0, 20 )
                y = 10 + random.uniform( 0, 20 )

                self.VPhysicsGetObject().ApplyTorqueCenter( AngularImpulse( x, y, 0 ) )

                # Since we just nudged the mine, ignore collisions with the world until
                # the mine is in the air. We only want to explode if the player tries to 
                # run over the mine before it jumps up.
                self.ignoreworldtime = gpGlobals.curtime + 1.0
                self.UpdateLight( True, 255, 0, 0, 190 )

                # use the correct bounce behavior
                if self.modification == self.MINE_MODIFICATION_CAVERN:
                    self.SetThink ( self.CavernBounceThink )
                    self.SetNextThink( gpGlobals.curtime + 0.15 )
                else:
                    self.SetThink( self.BounceThink )
                    self.SetNextThink( gpGlobals.curtime + 0.5 )

            elif iState is self.MINE_STATE_LAUNCHED:
                self.UpdateLight( True, 255, 0, 0, 190 )
                self.SetThink( None )
                self.SetNextThink( gpGlobals.curtime + 0.5 )

                self.SetTouch( self.ExplodeTouch )
                flags = self.VPhysicsGetObject().GetCallbackFlags()
                self.VPhysicsGetObject().SetCallbackFlags( flags | CALLBACK_GLOBAL_TOUCH_STATIC )
                
            else:
                DevMsg("**Unknown Mine State: %d\n", iState )

        def Flip(self, vecForce, torque):
            """ Bouncbomb flips to try to right itself, try to get off
                of and object that it's not allowed to clamp to, or 
                to get away from a hint node that inhibits placement
                of mines. """
            if self.flipattempts > self.BOUNCEBOMB_MAX_FLIPS:
                # Not allowed to try anymore.
                self.SetThink(None)
                return

            self.EmitSound( "NPC_CombineMine.FlipOver" )
            self.VPhysicsGetObject().ApplyForceCenter( vecForce )
            self.VPhysicsGetObject().ApplyTorqueCenter( torque )
            self.flipattempts += 1

        MINE_MIN_PROXIMITY_SQR = 676 # 27 inches
        def IsValidLocation(self): 
            pAvoidObject = None
            flAvoidForce = 0.0

            # Look for other mines that are too close to me.
            pEntity = gEntList.FirstEnt()
            vecMyPosition = self.GetAbsOrigin()
            while pEntity:
                if pEntity.GetClassname() == self.GetClassname() and pEntity != self:
                    # Don't lock down if I'm near a mine that's already locked down.
                    if vecMyPosition.DistToSqr(pEntity.GetAbsOrigin()) < self.MINE_MIN_PROXIMITY_SQR:
                        pAvoidObject = pEntity
                        flAvoidForce = 60.0
                        break

                pEntity = gEntList.NextEnt( pEntity )

            if pAvoidObject:
                # Build a force vector to push us away from the inhibitor.
                # Start by pushing upwards.
                vecForce = Vector( 0, 0, self.VPhysicsGetObject().GetMass() * 200.0 )

                # Now add some force in the direction that takes us away from the inhibitor.
                vecDir = self.GetAbsOrigin() - pAvoidObject.GetAbsOrigin()
                vecDir.z = 0.0
                VectorNormalize( vecDir )
                vecForce += vecDir * self.VPhysicsGetObject().GetMass() * flAvoidForce

                self.Flip( vecForce, AngularImpulse( 100, 0, 0 ) )

                # Tell the code that asked that this position isn't valid.
                return False

            return True

        def BounceThink(self):
            """ Release the spikes """
            self.SetNextThink( gpGlobals.curtime + 0.1 )
            self.StudioFrameAdvance()

            pPhysicsObject = self.VPhysicsGetObject()
            
            if pPhysicsObject != None:
            
                MINE_MAX_JUMP_HEIGHT = 200

                # Figure out how much headroom the mine has, and hop to within a few inches of that.
                tr = trace_t()
                UTIL_TraceLine( self.GetAbsOrigin(), self.GetAbsOrigin() + Vector( 0, 0, MINE_MAX_JUMP_HEIGHT ), MASK_SHOT, self, COLLISION_GROUP_INTERACTIVE, tr )

                if tr.ent and tr.ent.VPhysicsGetObject():
                    # Physics object resting on me. Jump as hard as allowed to try to knock it away.
                    height = MINE_MAX_JUMP_HEIGHT
                else:
                    height = tr.endpos.z - self.GetAbsOrigin().z
                    height -= self.BOUNCEBOMB_RADIUS
                    if height < 0.1:
                        height = 0.1
                

                time = math.sqrt( height / (0.5 * sv_gravity.GetFloat()) )
                velocity = sv_gravity.GetFloat() * time

                # or you can just AddVelocity to the object instead of ApplyForce
                force = velocity * pPhysicsObject.GetMass()

                up = Vector()
                self.GetVectors( None, None, up )
                pPhysicsObject.Wake()
                pPhysicsObject.ApplyForceCenter( up * force )

                pPhysicsObject.ApplyTorqueCenter( AngularImpulse( random.uniform( 5, 25 ), random.uniform( 5, 25 ), 0 ) )
                

                if self.nearestunit:
                    vecPredict = self.nearestunit.GetSmoothedVelocity()

                    pPhysicsObject.ApplyForceCenter( vecPredict * 10 )
                

                self.EmitSound( "NPC_CombineMine.Hop" )
                self.SetThink( None )

        def CavernBounceThink(self):
            """ A different bounce behavior for the citizen-modified mine. Detonates at the top of its apex, 
                and does not attempt to track enemies. """
            self.SetNextThink( gpGlobals.curtime + 0.1 )
            self.StudioFrameAdvance()

            pPhysicsObject = self.VPhysicsGetObject()

            if pPhysicsObject != None:
                MINE_MAX_JUMP_HEIGHT = 78

                # Figure out how much headroom the mine has, and hop to within a few inches of that.
                tr = trace_t()
                UTIL_TraceLine( self.GetAbsOrigin(), self.GetAbsOrigin() + Vector( 0, 0, MINE_MAX_JUMP_HEIGHT ), MASK_SHOT, self, COLLISION_GROUP_INTERACTIVE, tr )

                if tr.ent and tr.ent.VPhysicsGetObject():            
                    # Physics object resting on me. Jump as hard as allowed to try to knock it away.
                    height = MINE_MAX_JUMP_HEIGHT
                else:
                    height = tr.endpos.z - GetAbsOrigin().z
                    height -= BOUNCEBOMB_RADIUS
                    if height < 0.1:
                        height = 0.1

                time = math.sqrt( height / (0.5 * sv_gravity.GetFloat()) )
                velocity = sv_gravity.GetFloat() * time

                # or you can just AddVelocity to the object instead of ApplyForce
                force = velocity * pPhysicsObject.GetMass()

                up = Vector()
                self.GetVectors( None, None, up )
                
                pPhysicsObject.Wake()
                pPhysicsObject.ApplyForceCenter( up * force )
                if self.nearestunit:
                    vecPredict = self.nearestunit.GetSmoothedVelocity()

                    pPhysicsObject.ApplyForceCenter( vecPredict * (pPhysicsObject.GetMass() * 0.65) )

                pPhysicsObject.ApplyTorqueCenter( AngularImpulse( random.uniform( 15, 40 ), random.uniform( 15, 40 ), random.uniform( 30, 60 ) ) )
                
                self.EmitSound( "NPC_CombineMine.Hop" )

                self.SetThink( self.ExplodeThink )
                self.SetNextThink( gpGlobals.curtime + 0.33 )

        def CaptiveThink(self):
            self.SetNextThink( gpGlobals.curtime + 0.05 )
            self.StudioFrameAdvance()

            #phase = math.abs( math.sin( gpGlobals.curtime * 4.0 ) )
            #phase *= self.BOUNCEBOMB_HOOK_RANGE
            #self.SetPoseParameter( self.allhooks, phase )
            return

        def SettleThink(self):
            self.SetNextThink( gpGlobals.curtime + 0.05 )
            self.StudioFrameAdvance()

            if self.GetParent():
                # A scanner or something is carrying me. Just keep checking back.
                return

            # Not being carried.
            if not self.VPhysicsGetObject():
                # Probably was just dropped. Get physics going.
                self.CreateVPhysics()

                if not self.VPhysicsGetObject():
                    print("**** Can't create vphysics for combine_mine!\n" )
                    UTIL_Remove( self )
                    return

                self.VPhysicsGetObject().Wake()
                return

            if not self.disarmed:
                if self.VPhysicsGetObject().IsAsleep() and not (self.VPhysicsGetObject().GetGameFlags() & FVPHYSICS_PLAYER_HELD):
                
                    # If i'm not resting on the world, jump randomly.
                    tr = trace_t()
                    UTIL_TraceLine( self.GetAbsOrigin(), self.GetAbsOrigin() - Vector( 0, 0, 1024 ), MASK_SHOT|CONTENTS_GRATE, self, COLLISION_GROUP_NONE, tr )

                    bHop = False
                    if tr.ent:
                        pPhysics = tr.ent.VPhysicsGetObject()

                        if pPhysics and pPhysics.GetMass() <= 1000:
                            # Light physics objects can be moved out from under the mine.
                            bHop = True
                        elif tr.ent.takedamage != DAMAGE_NO:
                            # Things that can be harmed can likely be broken.
                            bHop = True

                        if bHop:
                            vecForce = Vector()
                            vecForce.x = random.uniform( -1000, 1000 )
                            vecForce.y = random.uniform( -1000, 1000 )
                            vecForce.z = 2500

                            torque = AngularImpulse( 160, 0, 160 )

                            self.Flip( vecForce, torque )
                            return

                        # Check for upside-down
                        vecUp = Vector()
                        self.GetVectors( None, None, vecUp )
                        if vecUp.z <= 0.8:
                            # Landed upside down. Right self
                            vecForce = Vector( 0, 0, 2500 )
                            self.Flip( vecForce, AngularImpulse( 60, 0, 0 ) )
                            return

                    # Check to make sure I'm not in a forbidden location
                    if not self.IsValidLocation():
                        return

                    # Lock to what I'm resting on
                    # constraint_ballsocketparams_t ballsocket
                    # ballsocket.Defaults()
                    # ballsocket.constraint.Defaults()
                    # ballsocket.constraint.forceLimit = lbs2kg(1000)
                    # ballsocket.constraint.torqueLimit = lbs2kg(1000)
                    # ballsocket.InitWithCurrentObjectState( g_PhysWorldObject, VPhysicsGetObject(), GetAbsOrigin() )
                    # self.constraint = physenv.CreateBallsocketConstraint( g_PhysWorldObject, VPhysicsGetObject(), None, ballsocket )
                    self.CloseHooks()

                    self.SetMineState( self.MINE_STATE_ARMED )
                
        def OnTakeDamage(self, info):
            if self.constraint or not self.VPhysicsGetObject():
                return False

            self.VPhysicsTakeDamage( info )
            return True
        
        def UpdateLight(self, bTurnOn, r, g, b, a):
            if bTurnOn:
                assert( a > 0 )

                # Throw the old sprite away
                if self.sprite:
                    UTIL_Remove( self.sprite )
                    self.sprite = None

                if not self.sprite:
                    up = Vector()
                    self.GetVectors( None, None, up )

                    # Light isn't on.
                    self.sprite = CSprite.SpriteCreate( "sprites/glow01.vmt", self.GetAbsOrigin() + up * 10.0, False )
                    pSprite = self.sprite

                    if self.sprite:
                        pSprite.SetParent( self )
                        pSprite.SetTransparency( kRenderTransAdd, r, g, b, a, kRenderFxNone )
                        pSprite.SetScale( 0.35, 0.0 )
                else:
                    # Update color
                    pSprite = self.sprite
                    pSprite.SetTransparency( kRenderTransAdd, r, g, b, a, kRenderFxNone )

            if not bTurnOn:
                if self.sprite:
                    UTIL_Remove( self.sprite )
                    self.sprite.Set( None )
            
            if not self.sprite:
                self.lastspritecolor.SetRawColor( 0 )
            else:
                self.lastspritecolor.SetColor( r, g, b, a )
                
        def IsAwake(self):
            return self.awake

        def Wake(self, bAwake):
            controller = CSoundEnvelopeController.GetController()

            filter = CReliableBroadcastRecipientFilter()
            
            if not self.warnsound:
                self.warnsound = controller.SoundCreate( filter, self.entindex(), "NPC_CombineMine.ActiveLoop" )
                controller.Play( self.warnsound, 1.0, PITCH_NORM  )

            if bAwake:
                # Turning on
                if self.foenearest:
                    self.EmitSound( "NPC_CombineMine.TurnOn" )
                    controller.SoundChangeVolume( self.warnsound, 1.0, 0.1 )

                r = g = b = 0

                if self.foenearest:
                    r = 255
                else:
                    g = 255

                self.UpdateLight( True, r, g, b, 190 )
            else:
                # Turning off
                if self.foenearest:
                    self.EmitSound( "NPC_CombineMine.TurnOff" )

                self.nearestunit = None
                controller.SoundChangeVolume( self.warnsound, 0.0, 0.1 )
                self.UpdateLight( False, 0, 0, 0, 0 )

            self.awake = bAwake

        def FindNearestNPC(self):
            """ Returns distance to the nearest BaseCombatCharacter. """
            flNearest = (self.BOUNCEBOMB_WARN_RADIUS * self.BOUNCEBOMB_WARN_RADIUS) + 1.0

            self.senses.ForcePerformSensing()
            self.nearestunit = self.senses.GetNearestEnemy()
            if self.nearestunit:
                flNearest = (self.GetAbsOrigin() - self.nearestunit.GetAbsOrigin()).LengthSqr()
               
                # Friend
                #UpdateLight( True, 0, 255, 0, 190 )
                #self.foenearest = False
                # Changing state to where a foe is nearest.
                self.UpdateLight( True, 255, 0, 0, 190 )
                self.foenearest = True

            return math.sqrt( flNearest )

        def SearchThink(self):
            # if( !UTIL_FindClientInPVS(edict()) )
                # # Sleep!
                # SetNextThink( gpGlobals.curtime + 0.5 )
                # return

            # if(	(CAI_BaseNPC::m_nDebugBits & bits_debugDisableAI) )
                # if( IsAwake() )
                    # Wake(False)

                # SetNextThink( gpGlobals.curtime + 0.5 )
                # return

            self.SetNextThink( gpGlobals.curtime + 0.1 )
            self.StudioFrameAdvance()

            if self.constraint and gpGlobals.curtime - self.timegrabbed >= 1.0:
                #m_OnPulledUp.FireOutput( self, self )
                self.SetMineState( self.MINE_STATE_CAPTIVE )
                return

            flNearestNPCDist = self.FindNearestNPC()

            if flNearestNPCDist <= self.BOUNCEBOMB_WARN_RADIUS:
                if not self.IsAwake():
                    self.Wake( True )
            else:
                if self.IsAwake():
                    self.Wake( False )
                return
            

            if flNearestNPCDist <= self.BOUNCEBOMB_DETONATE_RADIUS and self.foenearest:
                if self.bounce:
                    self.SetMineState( self.MINE_STATE_TRIGGERED )
                else:
                    # Don't pop up in the air, just explode if the NPC gets closer than explode radius.
                    self.SetThink( self.ExplodeThink )
                    self.SetNextThink( gpGlobals.curtime + self.explosiondelay )

        def ExplodeTouch(self, pOther):
            # Don't touch anything if held by physgun.
            if self.heldbyphysgun:
                return

            # Don't touch triggers.
            if pOther.IsSolidFlagSet(FSOLID_TRIGGER):
                return

            # Don't touch gibs and other debris
            if pOther.GetCollisionGroup() == COLLISION_GROUP_DEBRIS:
                vecVelocity = Vector()

                self.VPhysicsGetObject().GetVelocity( vecVelocity, None )

                if vecVelocity == vec3_origin:
                    self.ExplodeThink()

                return
            

            # Don't detonate against the world if not allowed. Actually, don't
            # detonate against anything that's probably not an NPC (such as physics props)
            if self.ignoreworldtime > gpGlobals.curtime and not pOther.IsUnit():
                return

            self.ExplodeThink()

        def ExplodeThink(self):
            self.SetSolid( SOLID_NONE )

            # Don't catch self in own explosion!
            self.takedamage = DAMAGE_NO

            if self.sprite:
                self.UpdateLight( False, 0, 0, 0, 0 )

            if self.warnsound:
                controller = CSoundEnvelopeController.GetController()
                controller.SoundDestroy( self.warnsound )

            pThrower = self.HasPhysicsAttacker( 0.5 )

            if self.modification == self.MINE_MODIFICATION_CAVERN:
                ExplosionCreate( self.GetAbsOrigin(), self.GetAbsAngles(), pThrower if pThrower else self, self.unitinfo.meleedamage, self.BOUNCEBOMB_EXPLODE_RADIUS, True,
                    None, CLASS_PLAYER_ALLY )
            else:
                ExplosionCreate( self.GetAbsOrigin(), self.GetAbsAngles(), pThrower if pThrower else self, self.unitinfo.meleedamage, self.BOUNCEBOMB_EXPLODE_RADIUS, True)
            
            UTIL_Remove( self )
        
        def OpenHooks(self, bSilent=False):
            if not bSilent:
                self.EmitSound( "NPC_CombineMine.OpenHooks" )

            if self.VPhysicsGetObject():
                # It's possible to not have a valid physics object here, since self function doubles as an initialization function.
                PhysClearGameFlags( self.VPhysicsGetObject(), FVPHYSICS_CONSTRAINT_STATIC )

                self.VPhysicsGetObject().EnableMotion( True )

            #self.SetPoseParameter( self.allhooks, self.BOUNCEBOMB_HOOK_RANGE )
            #filter = CPVSFilter(self.GetAbsOrigin())
            #self.SendEvent(filter, self.EVENT_HOOKOPEN)
            
        def CloseHooks(self):
            if not self.locksilently:
                self.EmitSound( "NPC_CombineMine.CloseHooks" )

            if self.VPhysicsGetObject():
                # It's possible to not have a valid physics object here, since self function doubles as an initialization function.
                PhysSetGameFlags( self.VPhysicsGetObject(), FVPHYSICS_CONSTRAINT_STATIC )

            # Only lock silently the first time we call self.
            self.locksilently = False

            #self.SetPoseParameter( self.allhooks, 0 )
            #filter = CPVSFilter(self.GetAbsOrigin())
            #self.SendEvent(filter, self.EVENT_HOOKCLOSE)

            self.VPhysicsGetObject().EnableMotion( False )

            # Once I lock down, forget how many tries it took.
            self.flipattempts = 0

        def InputDisarm(self, inputdata):
            # Only affect a mine that's armed and not placed by player.
            if not self.placedbyplayer and self.minestate == MINE_STATE_ARMED:
                if self.constraint:
                    physenv.DestroyConstraint( self.constraint )
                    self.constraint = None

                self.disarmed = True
                self.OpenHooks(False)

                self.SetMineState(self.MINE_STATE_DORMANT)

        # def OnPhysGunDrop(self, pPhysGunUser, Reason):
            # m_hPhysicsAttacker = pPhysGunUser
            # m_flLastPhysicsInfluenceTime = gpGlobals.curtime

            # self.timegrabbed = FLT_MAX

            # self.heldbyphysgun = False

            # if( self.minestate == MINE_STATE_ARMED )
            
                # # Put the mine back to searching.
                # Wake( False )
                # return
            

            # if( Reason == DROPPED_BY_CANNON )
            
                # # Set to lock down to ground again.
                # self.placedbyplayer = True
                # OpenHooks( True )
                # SetMineState( MINE_STATE_DEPLOY )
            
            # else if ( Reason == LAUNCHED_BY_CANNON )
            
                # SetMineState( MINE_STATE_LAUNCHED )
            
        # def HasPhysicsAttacker(self, dt):
            # if gpGlobals.curtime - dt <= m_flLastPhysicsInfluenceTime:
                # return m_hPhysicsAttacker
            # return None

        # def OnPhysGunPickup(self, pPhysGunUser, reason):
            # m_hPhysicsAttacker = pPhysGunUser
            # m_flLastPhysicsInfluenceTime = gpGlobals.curtime

            # self.flipattempts = 0

            # if reason != PUNTED_BY_CANNON:
            
                # if( self.minestate == MINE_STATE_ARMED )
                
                    # # Yanking on a mine that is locked down, trying to rip it loose.
                    # UpdateLight( True, 255, 255, 0, 190 )
                    # self.timegrabbed = gpGlobals.curtime
                    # self.heldbyphysgun = True

                    # VPhysicsGetObject().EnableMotion( True )

                    # # Try to scatter NPCs without panicking them. Make a move away sound up around their 
                    # # ear level.
                    # CSoundEnt::InsertSound( SOUND_MOVE_AWAY, GetAbsOrigin() + Vector( 0, 0, 60), 32.0f, 0.2f )
                    # return
                
                # else
                
                    # # Picked up a mine that was not locked down.
                    # self.heldbyphysgun = True

                    # if( self.minestate == MINE_STATE_TRIGGERED )
                    
                        # # self mine's already set to blow. Player can't place it.
                        # return
                    
                    # else
                    
                        # self.disarmed = False
                        # SetMineState( MINE_STATE_DEPLOY )
                    
                
            
            # else
            
                # self.heldbyphysgun = False
            

            # if( reason == PUNTED_BY_CANNON )
            
                # if( self.minestate == MINE_STATE_TRIGGERED or self.minestate == MINE_STATE_ARMED )
                
                    # # Already set to blow
                    # return
                

                # self.disarmed = False
                # self.placedbyplayer = True
                # SetTouch( None )
                # SetThink( &CBounceBomb::SettleThink )
                # SetNextThink( gpGlobals.curtime + 0.1)

                # # Since being punted causes the mine to flip, sometimes it 'catches an edge'
                # # and ends up touching the ground from whence it came, exploding instantly. 
                # # self little stunt prevents that by ignoring world collisions for a very short time.
                # self.ignoreworldtime = gpGlobals.curtime + 0.1

    # Vars
    minestate = -1
    locksilently = False
    disarmed = False
    foenearest = False
    warnsound = None
    nearestunit = None
    sprite = None
    constraint = None
    modification = 0
    senses = None
    
    fowflags = FOWFLAG_UNITS_MASK
    
    # Settings
    BOUNCEBOMB_HOOK_RANGE = 64
    BOUNCEBOMB_WARN_RADIUS = 245.0 # Must be slightly less than physcannon!
    BOUNCEBOMB_DETONATE_RADIUS = 100.0

    BOUNCEBOMB_EXPLODE_RADIUS = 320
    #BOUNCEBOMB_EXPLODE_DAMAGE = 150
    
    # After self many flips, seriously cut the frequency with which you try.
    BOUNCEBOMB_MAX_FLIPS = 5

    # Approximate radius of the bomb's model
    BOUNCEBOMB_RADIUS = 24
    
    # Mine states
    MINE_STATE_DORMANT = 0,
    MINE_STATE_DEPLOY = 1 # Try to lock down and arm
    MINE_STATE_CAPTIVE = 2 # Held in the physgun
    MINE_STATE_ARMED = 3 # Locked down and looking for targets
    MINE_STATE_TRIGGERED = 4 # No turning back. I'm going to explode when I touch something.
    MINE_STATE_LAUNCHED = 5 # Similar. Thrown from physgun.
    
    # Modifications
    MINE_MODIFICATION_NORMAL = 0
    MINE_MODIFICATION_CAVERN = 1
    
# Unit registration
class AbilityCombineMine(AbilityPlaceObjectShared, UnitInfo):
    name        = "combine_mine"
    cls_name    = "combine_mine"
    displayname = "#CombMine_Name"
    description = "#CombMine_Description"
    image_name = "vgui/abilities/ability_mine.vmt"
    image_dis_name = "vgui/abilities/ability_mine_dis.vmt"
    costs = [[('kills', 1)], [('requisition', 1)]]
    rechargetime = 15.0
    placemaxrange = 16.0
    modelname = "models/props_combine/combine_mine01.mdl"
    attributes = ['light']
    meleedamage = 200
    techrequirements = ['combine_mine_unlock']
    requirerotation = False
    activatesoundscript = '#deploymine'
    viewdistance = BounceBomb.BOUNCEBOMB_DETONATE_RADIUS*1.5
    population = 0
    
    def IsValidPosition(self, position):
        return True
    
    def PlaceObject(self):
        info = FindPositionInfo(self.targetpos, self.mins, self.maxs, 
                                startradius=72.0, radiusstep=120)
        mines = []
        for i in range(0, 3):
            UTIL_FindPosition(info)
            if not info.success:
                break
            object = CreateUnitNoSpawn(self.name, self.ownernumber)
            if not object:
                break
            object.SetAbsOrigin(info.position)
            object.SetAbsAngles(self.targetangle)
            DispatchSpawn(object)
            object.Activate()
            if object.unitinfo.zoffset:
                object.SetAbsOrigin(object.GetAbsOrigin()+Vector(0,0,object.unitinfo.zoffset))
            mines.append(object)
        return mines
    
class AbilityCombineMineUnlock(AbilityUpgrade):
    name = 'combine_mine_unlock'
    displayname = '#AbilityCombineMineUnlock_DisplayName'
    description = '#AbilityCombineMineUnlock_Description'
    image_name = "vgui/abilities/ability_mine.vmt"
    buildtime = 120.0
    costs = [[('kills', 5)], [('requisition', 5)]]
    
class OverrunAbilityCombineMine(AbilityCombineMine):
    name = 'overrun_combine_mine'
    hidden = True
    
    