Azeroth Survivors - unlock everything + game patches
====================================================

EASY WAY (nothing to install): double-click azs-unlocker.html. It opens in your browser,
works offline and uploads nothing. Pick your save / game exe, download the result, done.
The page explains where the files are.

The rest of this file is for the command-line version (azs_tool.py), which does the same
and needs Python 3 (python.org on Windows; tick "Add python.exe to PATH" while installing).
CLOSE THE GAME before running anything, or it will overwrite the changes on exit.


1) Unlock everything in your save
---------------------------------
    python azs_tool.py unlock

This finds your save on its own (%APPDATA%\wenilla-rogue\characters.txt). If your save
is somewhere else (Linux/Proton prefix, Steam Deck, ...), give the path:

    python azs_tool.py unlock "/path/to/wenilla-rogue/characters.txt"

What it does, for all 9 classes:
  - every zone opened and beaten, Naxxramas included
  - all gear pieces collected (every tier)
  - every ring, trinket and amulet seen in the codex
  - every achievement, which also unlocks the perks, companions and tabards behind them
  - enough talent experience for every talent point (spend them in the Talents tab)
  - lifetime stats raised to the achievement thresholds (1,000,000 kills, 50 wins, ...)

It keeps your heroes, equipped gear, spent talents and settings, and leaves a backup
next to the save (characters.txt.before-unlock-<date>.bak).


2) Game patches (optional)
--------------------------
Sixteen patches for the game exe, use any combination:

  talents  The game normally stops at 51 talent points. Each class can now earn 129,
           enough to max all three talent trees.
  caches   Battleground caches (the chests elites drop) cost no gold, so all your gold
           goes to rerolls. The cache price also stops climbing; reroll and skip prices
           are tied to it, so they stay at their starting level. Walk over a cache to open
           it: one opens at a time, and any others stay on the ground until you've picked.
           The HUD shows the cache price as 0.
  bosses   The big bosses that arrive every few minutes (Hogger and co.) normally give no
           treasure. Now each one gives a treasure with legendary rewards. Guardian and
           elite treasures stay as they were.
  gold     Every run starts with 20 gold instead of none.
  banish   Every run starts with 20 banishes, whatever your Banish perk rank.
  rerolls  Every run starts with 10 free rerolls, whatever your perk rank. After
           those, rerolls cost gold as usual.
  classes  Hunter: every Auto Shot forks to 2 enemies and chains to 3 more, each
           for its full damage; 5% of them hit 4 more on top (Thunderfury), and
           5% slow their target by 20% for 5 sec; Hunters can hold 7 abilities.
           Frenzy carries this, so spend a point in it (Piercing Shots' single
           extra hit is folded into it). Shadow Priest: the Shadowform capstone also
           starts runs with Devouring Plague, Mind Flay and Mind Blast. Affliction
           Warlock: the Seed of Corruption capstone also starts runs with Drain
           Life and Curse of Agony.
  tfvisual Chain Lightning uses the Thunderfury spell's visuals and icon (WoW
           spell 21992), so the proc looks like the real thing. Shaman Chain
           Lightning looks like it too.
  tfweapon The starting Worn Dagger is shown as Thunderfury (name and model), on
           every hero that shows it.
  density  The enemy density slider goes up to 1000%. Kills give a quarter of
           the XP they would at 100% density, and gold as at 100%, whatever
           you set it to.
  firstcache  The first battleground cache you open in a run offers only
           legendary amulets, so you can pick the amulet your run is built around.
  luck     Every race starts with 100% luck (Gnomes keep their +20% on top).
  mindflay Mind Flay channels on every enemy in range (like Drain Life does on
           one), so you don't have to face your targets.
  lifesteal  Shaman, Mage and Druid start with 1% lifesteal (the other classes
           already start with some).
  cacherate  Battleground caches spawn twice as often (every 35 sec, not 70).
  guardians  When a guardian dies, its lair spawns a new one at once instead of
           3 minutes later. Each still drops its treasure, and they keep
           growing stronger.

Run from the game folder (no names = all sixteen patches):

    python azs_tool.py patch
    python azs_tool.py patch talents
    python azs_tool.py patch caches bosses

or point it at the exe:

    python azs_tool.py patch "C:\Games\AzerothSurvivors\AzerothSurvivors.exe" caches

It only patches the exact game version these were made for (or an exe it already patched,
to add more patches or update an older one) and refuses anything else. The exe from before
is kept next to it (AzerothSurvivors.exe.before-patch-<date>.bak). If the game updates
itself, run it again; if the update changed the exe, it will say so and do nothing.
Without the talents patch, the unlock still gives you the normal 51 points.


Undo
----
Copy the .bak file back over characters.txt (or AzerothSurvivors.exe).


Extras
------
    python azs_tool.py decode characters.txt plain.txt    readable copy of a save
    python azs_tool.py encode plain.txt characters.txt    seal an edited copy again
