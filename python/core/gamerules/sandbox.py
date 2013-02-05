from base import WarsBaseGameRules
from info import GamerulesInfo

class Sandbox(WarsBaseGameRules):
    def SetupGame(self, gamelobby_players, gamelobby_customfields):
        super(Sandbox, self).SetupGame(gamelobby_players, gamelobby_customfields)
 
class SandBoxInfo(GamerulesInfo):
    name = 'sandbox'
    displayname = '#Sandbox_Name'
    description = '#Sandbox_Description'
    cls = Sandbox
    huds = [
        'core.hud.HudSandbox', 
        'core.hud.HudDirectControl',
        'core.hud.HudPlayerNames',
    ]
    allowplayerjoiningame = True