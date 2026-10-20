#!/usr/bin/env python3
"""Azeroth Survivors save unlocker and game patcher.

  python azs_tool.py unlock [SAVE]                   unlock zones, gear, codex, achievements, talent XP
  python azs_tool.py patch  [EXE] [talents] [caches] [bosses] [gold] [banish] [rerolls] [classes] [tfvisual] [tfweapon] [density] [firstcache] [luck]
                                     patch the game (all of them if none is named):
                                       talents  talent cap 51 -> 129
                                       caches   battleground caches cost no gold
                                       bosses   big bosses give a legendary treasure
                                       gold     start every run with 20 gold
                                       banish   20 banishes per run
                                       rerolls  10 free rerolls per run
                                       classes  Hunter Thunderfury proc + 7 slots, Shadow/Affliction capstones
                                       tfvisual  Chain Lightning looks like Thunderfury (Shaman too)
                                       tfweapon  starter Worn Dagger shows as Thunderfury
                                       density  kill XP/gold as at 100% density
                                       firstcache  first cache of a run: legendary amulets
                                       luck     every race starts with 100% luck
  python azs_tool.py decode SAVE OUT / encode TXT SAVE

SAVE defaults to the game's save (%APPDATA%\\wenilla-rogue\\characters.txt, or
$WOW_ROGUE_SAVE). EXE defaults to AzerothSurvivors.exe in the current folder.
Both commands keep a backup next to the file they change. Close the game first.
"""
import base64, hashlib, hmac, os, shutil, struct, sys, time

# ---------------------------------------------------------------- save codec
# "RSE1:" + base64( nonce[16] || ciphertext || tag[20] )
#   tag       = HMAC-SHA1(KEY, b"tag" || nonce || ciphertext)
#   keystream = HMAC-SHA1(KEY, b"ks" || nonce || u64le(block)) per 20-byte block
KEY = b"azeroth-survivors/save/v1/" + bytes.fromhex("9c4e27d16af013b85de2710ca936c48f")


def _h(*parts):
    return hmac.new(KEY, b"".join(parts), hashlib.sha1).digest()


def _xor(nonce, data):
    out = bytearray(data)
    for i in range(0, len(out), 20):
        ks = _h(b"ks", nonce, struct.pack("<Q", i // 20))
        for j in range(min(20, len(out) - i)):
            out[i + j] ^= ks[j]
    return bytes(out)


def decode(text):
    text = text.strip()
    if not text.startswith("RSE1:"):
        return text  # already a plain (unsealed) save
    raw = base64.b64decode(text[5:])
    nonce, ct, tag = raw[:16], raw[16:-20], raw[-20:]
    if not hmac.compare_digest(_h(b"tag", nonce, ct), tag):
        raise ValueError("save is damaged (tag mismatch)")
    return _xor(nonce, ct).decode("utf-8")


def encode(plain):
    nonce = os.urandom(16)
    ct = _xor(nonce, plain.encode("utf-8"))
    return "RSE1:" + base64.b64encode(nonce + ct + _h(b"tag", nonce, ct)).decode()


# ---------------------------------------------------------------- unlock
CLASSES = {1: "warrior", 2: "paladin", 3: "hunter", 4: "rogue", 5: "priest",
           7: "shaman", 8: "mage", 9: "warlock", 11: "druid"}
WEAPONS = {1: 1, 2: 1, 3: 1, 4: 2, 5: 1, 7: 2, 8: 1, 9: 1, 11: 1}
ZONES = ["elwynn", "duskwood", "wsg", "ungoro", "ab", "feralas", "arena", "sm", "av", "brm", "aq", "naxx"]
CODEX = ["accuria", "quick_strike", "dark_iron", "dragonslayer", "archimtiros", "devoured", "spell_power",
         "seal_damned", "blooddrinker", "earthstrike", "tep", "lifegiving", "hoj", "blackhand", "carrot",
         "remote", "insignia", "eldre_thalas", "chosen", "onyxia_blood", "war_horn", "soulstone",
         "mark_of_fordring", "star_of_mystaria", "talvash", "south_seas_kelp", "prestor", "animated_chain",
         "woven_ivy", "darkmoon", "jeklik", "eye_of_hakkar", "steadfast_might", "enlightenment", "vek_nilash",
         "fallen_dragon", "malice_stone", "onyxia_tooth", "fire_lord"]
ACHIEVEMENTS = (
    [f"class:{c}" for c in CLASSES.values()] + [f"classlast:{c}" for c in CLASSES.values()]
    + [f"zone:{z}" for z in ZONES] + [f"zone9:{z}" for z in ZONES]
    + ["talents:1", "talents:9", "pieces:25", "pieces:100", "pieces:250", "pieces:all", "legendaryset",
       "codex:50", "codex:100"]
    + ["feat:" + f for f in ["kills2500", "kills6000", "lairs", "endless25", "endless30", "endless40",
                             "bare", "thrifty", "odds", "nou"]]
    + ["count:" + c for c in ["kills10k", "kills100k", "kills1m", "gold5k", "gold50k", "guardians100",
                              "guardians500", "bosses100", "caches100", "runs10", "runs100", "wins50"]])
STAT_MIN = {"kills": 1000000, "gold": 50000, "guardians": 500, "bosses": 100, "runs": 100, "wins": 50,
            "caches": 100}
TALENT_XP = 134160  # all 129 points with the patched exe (23205 covers the stock 51)


def _kv(s):
    return dict(x.split("=", 1) for x in s.split(",") if x)


def unlock(plain):
    lines = [l for l in plain.rstrip("\n").split("\n") if l]
    items = {100000 + c * 1000 + p * 100 + t * 10 for c, w in WEAPONS.items() for p in range(8 + w) for t in range(6)}
    now = str(int(time.time()))
    out, talents = [], {}
    single = {"items": "", "seen": "", "ach": "", "achat": "", "stat": ""}
    for l in lines:
        tag, _, rest = l.partition("|")
        if tag in ("open", "beat"):
            continue
        if tag in single:
            single[tag] = rest
            out.append(tag)  # placeholder, filled in below
        elif tag == "talent":
            c, xp, spent = rest.split("|", 2)
            talents[c] = (int(xp), spent)
            out.append("talent|" + c)
        else:
            out.append(l)

    have = {int(x) for x in single["items"].split(",") if x}
    seen = _kv(single["seen"]); seen.update({k: "4" for k in CODEX})
    ach = {x for x in single["ach"].split(",") if x} | set(ACHIEVEMENTS)
    achat = _kv(single["achat"])
    for k in ACHIEVEMENTS:
        achat.setdefault(k, now)
    stat = _kv(single["stat"])
    for k, v in STAT_MIN.items():
        stat[k] = str(max(int(stat.get(k, 0)), v))
    filled = {
        "items": "items|" + ",".join(map(str, sorted(have | items))),
        "seen": "seen|" + ",".join(f"{k}={v}" for k, v in sorted(seen.items())),
        "ach": "ach|" + ",".join(sorted(ach)),
        "achat": "achat|" + ",".join(f"{k}={v}" for k, v in sorted(achat.items())),
        "stat": "stat|" + ",".join(f"{k}={v}" for k, v in stat.items()),
    }
    res = []
    for l in out:
        if l in filled:
            res.append(filled.pop(l))
        elif l.startswith("talent|"):
            c = l[7:]
            xp, spent = talents[c]
            res.append(f"talent|{c}|{max(xp, TALENT_XP)}|{spent}")
        else:
            res.append(l)
    res += filled.values()  # sections the save did not have yet
    res += [f"talent|{c}|{TALENT_XP}|" for c in map(str, CLASSES) if c not in talents]
    res += [f"open|{c}|naxx" for c in CLASSES]
    res += [f"beat|{c}|" + ",".join(ZONES) for c in CLASSES]
    return "\n".join(res) + "\n"


def default_save():
    if os.environ.get("WOW_ROGUE_SAVE"):
        return os.environ["WOW_ROGUE_SAVE"]
    return os.path.join(os.environ.get("APPDATA", "."), "wenilla-rogue", "characters.txt")


def backup(path, tag):
    stem = f"{path}.{tag}-{time.strftime('%Y%m%d-%H%M%S')}"
    dst, n = stem + ".bak", 1
    while os.path.exists(dst):  # never overwrite an earlier backup
        n += 1
        dst = f"{stem}-{n}.bak"
    shutil.copy2(path, dst)
    return dst


def cmd_unlock(path=None):
    path = path or default_save()
    plain = decode(open(path, encoding="utf-8").read())
    bak = backup(path, "before-unlock")
    new = unlock(plain)
    assert decode(encode(new)) == new
    open(path, "w", encoding="utf-8").write(encode(new))
    print(f"unlocked {path}\nbackup: {bak}")


# ---------------------------------------------------------------- exe patches
# Each patch is a list of (file offset, original bytes, patched bytes) for one exact game build.
#
# talents: point n costs 80 + 15*n XP; the game counts points in a loop unrolled by three that
#   stops at `cmp reg, 0x36b` and then returns 51. Raise both to 129 points (bound 0x7fd).
# caches:  in the cache purchase routine, skip the "needs gold" check, take no gold, and keep
#   the price from climbing (reroll and skip prices are derived from it). Walking over a cache
#   only opens it when no cache treasure is already queued, so the treasure window closes after
#   each pick instead of chaining through every cache picked up at once. Caches start a run at
#   price 0 (was 20), so the HUD shows them as free; rerolls/skips use their minimums either way.
# bosses:  big bosses (Hogger and co.) normally give no treasure. On a boss kill, also queue the
#   bonus treasure guardians give and count it in a "boss treasures" counter (a spare dword at the
#   end of .data). When that treasure is dealt and the counter is set, its rarity-roll luck bonus is
#   1,000,000 instead of 0.25 (weights 60 : 25L : 10L^2 : 4L^3 : L^4), so it is legendary; picking a
#   reward uses the mark up. Guardian and elite treasures roll as before. The new code lives in three
#   int3 padding gaps in .text.
# gold:    the run setup zeroes shield and gold together; start every run with 20 gold instead.
# banish:  every run starts with 20 banishes, whatever the Banish perk rank. Using one only needs
#   the count to be non-zero, so nothing else caps it.
# rerolls: every run starts with 10 free rerolls, whatever the reroll perk rank; after those,
#   rerolls cost gold as usual.
# classes: Hunter: every Auto Shot that lands has a 5% chance to cast a free Chain Lightning (no
#   cooldown, slows 20% for 12 sec); runs start with Chain Lightning and Hunters may hold 7 abilities;
#   carried by Frenzy, which keeps what it does. Shadow Priest: the Shadowform capstone also starts
#   runs with Devouring Plague, Mind Flay and Mind Blast. Affliction Warlock: the Seed of Corruption
#   capstone also starts runs with Drain Life and Curse of Agony.
# tfvisual: Chain Lightning uses WoW spell 21992 (Thunderfury) for its visuals and icon instead of
#   421, so the proc looks like Thunderfury. Shaman Chain Lightning looks like it too.
# tfweapon: the starter Worn Dagger shows as Thunderfury (name and model), for every hero that shows it.
# density: kills give XP and gold as if enemy density were 100%, whatever it is set to (more
#   enemies still spawn).
# firstcache: the first battleground cache you open in a run offers only legendary amulets.
# luck: every race starts with 100% luck (Gnomes get their +20% on top).
_CMP = [1411633, 1411713, 1411926, 1413327, 2083186, 92748959, 92752017, 92752273, 92752574, 92796315,
        92805761, 93003212, 93006366, 93006494, 93006622, 93006750, 93006878, 93007006, 93007134, 93007266]
_MOV = [1411640, 1411720, 1411933, 1413335, 92748966, 92752024, 92752280, 92752581, 92796323, 92805768,
        93003220, 93006374, 93006502, 93006630, 93006758, 93006886, 93007014, 93007142, 93007274]
PATCHES = {
    "talents": [(o, "6b030000", "fd070000") for o in _CMP] + [(o, "33000000", "81000000") for o in _MOV],
    "caches": [(93639589, "4429f8", "0f1f00"),                   # sub eax, r15d           -> nop
               (93639592, "0f82c6000000", "660f1f440000"),       # jb needs-gold           -> nop
               (93639659, "899698090000", "660f1f440000"),       # store new price         -> nop
               (93450587, "80b9c709000000", "83b95809000000"),   # walk-over: click option -> treasure queued?
               (93450596, "80b9ca09000000", "ebaa0f1f440000"),   # queued: leave it on the ground
               (93411154, "14000000", "00000000")],              # run setup: cache price 20 -> 0
    # cave A (big boss killed), cave B (deal bonus treasure), cave C (reward picked), their three
    # hooks, and the .data VirtualSize (0x4c848 -> 0x4d000) so the counter at 0x147fe0ff0 is in-section
    "bosses": [
        (5078288, "cccccccccccccccccccccccccccccccccccccccccccccc",
         "ff8698060000ff8660090000ff05ce86b007e918664605"),
        (5062028, "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
         "488d4df0833d59c6b00700740af30f10158b46a505eb08f30f101539008805e98d074805"),
        (4979210, "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
         "8b865c09000083f80183d0ff89865c090000833dcd09b207007406ff0dc509b207e9c3604905"),
        (93578041, "ff8698060000",
         "e9d299b9fa90"),
        (93668657, "488d4df0f30f1015a7f83f00",
         "e956f8b7fa0f1f8000000000"),
        (93674209, "8b865c09000083f80183d0ff89865c090000",
         "e9249fb6fa0f1f8400000000000f1f440000"),
        (616, "48c80400",
         "00d00400"),
    ],
    # run setup zeroes shield+gold with one qword store; detour it into the int3 gap after cave A:
    # shield = 0, gold = 20, jump back
    "gold": [(5078311, "cccccccccccccccccccccccccccccccccccccccccccccccccc",
              "c7854c04000000000000c7855004000014000000e9cbd64305"),
             (93410304, "48c7854c04000000000000", "e92229bcfa660f1f440000")],
    # run setup copies the starting banish count from the run config; detour the load into the int3
    # gap after cave B: eax = 20, jump back to the original store
    "banish": [(5062064, "cccccccccccccccccccccccccc", "b814000000e9091d4405cccccc"),
               (93412029, "8b856c0b0000", "e9eee2bbfa90")],
    # run setup stores the free reroll count from edi; detour it into the int3 gap after cave C:
    # rerolls = 10, jump back
    "rerolls": [(4979248, "cccccccccccccccccccccccccccccc", "c785f40400000a000000e9245a4505"),
                (93410397, "89bdf4040000", "e9cea5bafa90")],
    # class changes, one option because their new effect lists share one set of .reloc blocks:
    #  - Hunter: Frenzy keeps its effect and also carries Thunderfury: 20% / 12 sec slow on Chain Lightning
    #    hits (kind 8), "start every run with Chain Lightning" (kind 27; a proc only casts an ability the
    #    hero owns) and 5% free Chain Lightning when an Auto Shot lands (kind 0, trigger 1, filter auto_shot).
    #    List and description live past .text's VirtualSize. Hunters may hold 7 abilities (detour on the
    #    level-up "cmp rsi,5" checking class byte [state+0x29c] == 3).
    #  - Shadow Priest: Shadowform capstone also starts with Devouring Plague, Mind Flay, Mind Blast
    #    (6-entry list in .pdata's file slack).
    #  - Affliction Warlock: Seed of Corruption capstone also starts with Drain Life and Curse of Agony
    #    (4-entry list in .rsrc's file slack).
    #  The three lists' pointers get .reloc blocks (the image uses ASLR); the sections grow to cover them.
    "classes": [
        (97831024, "00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
         "000000000000403f00000000000000009a801747010000000a000000000000000000000000000000060000000000000000000000000000000000000000000000080000000000803f01000000cdcc4c3e00004041000000000000000000000000010000000000000095f21747010000000f0000000000000000000000000000001b0000000000000095f21747010000000f000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000cdcc4c3d000000000000000095f21747010000000f000000000000000100000000000000010000000000000021cfb846010000000900000000000000"),
        (97831280, "00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
         "4d696c6573746f6e652e205065742062697465733a207b767d25206368616e6365206f6620612066726565204d756c74692d53686f742e205374617274207769746820436861696e204c696768746e696e673b206c616e646564204175746f2053686f747320686176652061203525206368616e636520746f20636173742069742028736c6f777320323025292e"),
        (118976856, "a8801747010000000100000000000000",
         "70d4d445010000000400000000000000"),
        (118976872, "e8801747010000004900000000000000",
         "70d5d445010000008e00000000000000"),
        (536, "6ec4d405",
         "fec5d405"),
        (5101723, "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
         "488b854001000080b89c0200000375064883fe06eb044883fe050f871e704705e9856d4705"),
        (93668923, "4883fe050f8794020000",
         "e95b92b8fa0f1f440000"),
        (138227776, "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
         "19000000713c000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000b0100000ad7233d0000c040d04400000000000000000000010000000000000071e31747010000000700000000000000000000000000000000000000000000000e00000001000000010000000000000071e3174701000000070000000000000000000000000000000000000000000000000000000000000000000000000000001b00000000000000afd2b846010000001000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000001b0000000000000098d2b846010000000900000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000001b000000000000006ed2b846010000000a0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"),
        (119003696, "88e91747010000000300000000000000",
         "407e3d48010000000600000000000000"),
        (656, "346e3f00",
         "c06f3f00"),
        (138438912, "00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
         "1b000000000000004f411847010000000a00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000b0100008fc2f53c0000c040d04400000000000000000000040600000000000000000000000000000000000000000000000000000000000000000000000000001b00000000000000afd7b846010000000a00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000001b0000000000000077d7b846010000000e0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"),
        (119027536, "10471847010000000200000000000000",
         "00b74048010000000400000000000000"),
        (696, "00370300",
         "00380300"),
        (139728088, "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
         "00d0d4051400000080a4d8a4f8a440a560a5000000703d0814000000a0aed0ae08af48af88af000000b040081000000008a788a7c8a70000"),
        (736, "d8aa1300",
         "10ab1300"),
        (444, "d8aa1300",
         "10ab1300"),
    ],
    # Chain Lightning's WoW spell id (used for its visuals and icon) 421 -> 21992 "Thunderfury";
    # affects every Chain Lightning, the Shaman's too
    "tfvisual": [(112783872, "a5010000", "e8550000")],
    # the starter Worn Dagger (WoW item 2092) record: name -> "Thunderfury, Blessed Blade of the Windseeker",
    # display 6442 -> 30606 (the model the game uses for its own Thunderfury)
    "tfweapon": [
        (112832680, "90c0b946010000000b00000000000000",
         "30e6b946010000002c00000000000000"),
        (112832700, "2a190000",
         "8e770000"),
    ],
    # kill rewards: the death handler turns the density option into a drop chance (1.65 / density);
    # load 100 instead of the option in both reward blocks, so kills pay out as at 100% density
    "density": [
        (93578948, "0fb78648020000", "b8640000006690"),  # movzx eax,[rsi+0x248] -> mov eax,100
        (93579035, "0fb78648020000", "b8640000006690"),  # movzx eax,[rsi+0x248] -> mov eax,100
    ],
    # cache hands are dealt with luck 0; detour into an int3 gap: if this is the run's first cache
    # (caches opened this run == 1) use luck 1,000,000 so every card is legendary; and in the card loop,
    # make every card of that hand an amulet card (kind 1)
    "firstcache": [
        (4981780, "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
         "488d4df083bea006000001750af30f10150380a605eb030f57d2e90a414905"),
        (93668619, "488d4df00f57d2eb29",
         "e904bfb6fa0f1f4000"),
        (5042392, "cccccccccccccccccccccccccccccccccccccccccccccccccccccc",
         "498b45004183bea0060000017505b8010000004885c0e9a9d44805"),
        (93701525, "498b45004885c0",
         "e93e2bb7fa6690"),
    ],
    # run setup stores (1,1,0,1) over four floats, the third being luck (+0x49c); detour that store into an
    # int3 gap, then also write luck = 1.0 (100%), as if every race had +100% luck (Gnomes keep their +20%)
    "luck": [
        (5028702, "cccccccccccccccccccccccccccccccccccccccccccccc",
         "440f119dc4040000c785cc0400000000803fe9d8984405"),
        (93410373, "440f119dc4040000",
         "e91467bbfa0f1f00"),
    ],
}
DESCRIBE = {"talents": "talent cap 51 -> 129", "caches": "caches cost no gold",
            "bosses": "big bosses give a legendary treasure", "gold": "start every run with 20 gold",
            "banish": "20 banishes per run", "rerolls": "10 free rerolls per run",
            "classes": "class changes (Hunter Thunderfury + 7 slots, Shadow Priest and Affliction capstones)",
            "tfvisual": "Chain Lightning looks like Thunderfury",
            "tfweapon": "starter Worn Dagger shows as Thunderfury", "density": "kill rewards ignore enemy density", "firstcache": "first cache of a run: legendary amulets",
            "luck": "every race starts with 100% luck"}
STOCK_SHA256 = "3b46bad92e7771afa61c93658fd850937834a40f3671af8b1a3e1d2aeb8b63c7"
# edits from earlier releases that are always undone (the first "gold" patch hit the wrong field)
RETIRED = [(93410230, "00000000", "14000000"),
           (5062064, "cccccccccccccccccccccccccc", "8b856c0b000001c0e9061d4405"),  # "double banishes" body
           (5062064, "cccccccccccccccccccccccccc", "b80a000000e9091d4405cccccc"),  # "10 banishes" body
           (118975144, "000000000000403f00000000000000009a801747010000000a0000000000000000000000000000000600000000000000",
            "00000000cdcc4c3d000000000000000095f21747010000000f0000000000000007000000000000000000000000000000"),  # first Thunderfury version (replaced Frenzy)
           (118976824, "7d801747010000000600000000000000",
            "30e6b946010000000b00000000000000"),  # first Thunderfury version (replaced Frenzy)
           (118976880, "4900000000000000",
            "4800000000000000"),  # first Thunderfury version (replaced Frenzy)
           (118975208, "4d696c6573746f6e652e20596f757220706574732720626974657320686176652061207b767d25206368616e636520746f206669726520612066726565204d756c74692d53686f74",
            "5468756e646572667572793a20656163682073686f74206861732061207b767d25206368616e636520746f20636173742061206672656520436861696e204c696768746e696e672e"),  # first Thunderfury version (replaced Frenzy)
           (97831024, "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
            "000000000000403f00000000000000009a801747010000000a000000000000000000000000000000060000000000000000000000cdcc4c3d000000000000000095f21747010000000f0000000000000007000000000000000000000000000000"),  # second Thunderfury version (0x30-byte entries, froze the game)
           (97831120, "00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
            "4d696c6573746f6e652e20596f757220706574732720626974657320686176652061207b767d25206368616e636520746f206669726520612066726565204d756c74692d53686f742e205468756e646572667572793a2065766572792073686f7420796f752066697265206861732061203525206368616e636520746f20636173742061206672656520436861696e204c696768746e696e672e"),  # second Thunderfury version (0x30-byte entries, froze the game)
           (118976872, "e8801747010000004900000000000000",
            "d0d4d445010000009a00000000000000"),  # second Thunderfury version (0x30-byte entries, froze the game)
           (536, "6ec4d405",
            "6ac5d405"),  # second Thunderfury version (0x30-byte entries, froze the game)
           (139728088, "000000000000000000000000",
            "00d0d4050c00000080a4b0a4"),  # second Thunderfury version (0x30-byte entries, froze the game)
           (97831024, "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
            "000000000000403f00000000000000009a801747010000000a00000000000000000000000000000006000000000000000000000000000000000000000000000000000000cdcc4c3d000000000000000095f21747010000000f000000000000000700000000000000000000000000000000000000000000000000000000000000"),  # third Thunderfury version (2 effects)
           (97831152, "00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
            "4d696c6573746f6e652e20596f757220706574732720626974657320686176652061207b767d25206368616e636520746f206669726520612066726565204d756c74692d53686f742e205468756e646572667572793a2065766572792073686f7420796f752066697265206861732061203525206368616e636520746f20636173742061206672656520436861696e204c696768746e696e672e"),  # third Thunderfury version (2 effects)
           (118976856, "a8801747010000000100000000000000",
            "70d4d445010000000200000000000000"),  # third Thunderfury version (2 effects)
           (118976872, "e8801747010000004900000000000000",
            "f0d4d445010000009a00000000000000"),  # third Thunderfury version (2 effects)
           (536, "6ec4d405",
            "8ac5d405"),  # third Thunderfury version (2 effects)
           (139728088, "000000000000000000000000",
            "00d0d4050c00000080a4c0a4"),  # third Thunderfury version (2 effects)
           (736, "d8aa1300",
            "e4aa1300"),  # third Thunderfury version (2 effects)
           (444, "d8aa1300",
            "e4aa1300"),  # third Thunderfury version (2 effects)
           (97831024, "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
            "000000000000403f00000000000000009a801747010000000a000000000000000000000000000000060000000000000000000000000000000000000000000000080000000000803f01000000cdcc4c3e00004041000000000000000000000000010000000000000095f21747010000000f00000000000000000000000000000000000000cdcc4c3d000000000000000095f21747010000000f000000000000000700000000000000000000000000000000000000000000000000000000000000"),  # fourth Thunderfury version (proc on every shot)
           (97831216, "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
            "4d696c6573746f6e652e20596f757220706574732720626974657320686176652061207b767d25206368616e636520746f206669726520612066726565204d756c74692d53686f742e205468756e646572667572793a2065766572792073686f74206861732061203525206368616e636520746f20636173742061206672656520436861696e204c696768746e696e672c20776869636820736c6f7773207768617420697420686974732062792032302520666f72203132207365632e"),  # fourth Thunderfury version (proc on every shot)
           (118976872, "e8801747010000004900000000000000",
            "30d5d44501000000bd00000000000000"),  # fourth Thunderfury version (proc on every shot)
           (536, "6ec4d405",
            "edc5d405"),  # fourth Thunderfury version (proc on every shot)
           (139728088, "00000000000000000000000000000000",
            "00d0d4051000000080a4d8a400a50000"),  # fourth Thunderfury version (proc on every shot)
           (97831024, "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
            "000000000000403f00000000000000009a801747010000000a000000000000000000000000000000060000000000000000000000000000000000000000000000080000000000803f01000000cdcc4c3e00004041000000000000000000000000010000000000000095f21747010000000f00000000000000000000000000000000000000cdcc4c3d000000000000000095f21747010000000f000000000000000100000000000000010000000000000021cfb846010000000900000000000000"),  # fifth Thunderfury version (no ability grant)
           (97831216, "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
            "4d696c6573746f6e652e20596f757220706574732720626974657320686176652061207b767d25206368616e636520746f206669726520612066726565204d756c74692d53686f742e205468756e646572667572793a2065616368204175746f2053686f742074686174206c616e6473206861732061203525206368616e636520746f20636173742061206672656520436861696e204c696768746e696e672c20736c6f77696e67207768617420697420686974732062792032302520666f72203132207365632e"),  # fifth Thunderfury version (no ability grant)
           (118976856, "a8801747010000000100000000000000",
            "70d4d445010000000300000000000000"),  # fifth Thunderfury version (no ability grant)
           (118976872, "e8801747010000004900000000000000",
            "30d5d44501000000c800000000000000"),  # fifth Thunderfury version (no ability grant)
           (536, "6ec4d405",
            "f8c5d405"),  # fifth Thunderfury version (no ability grant)
           (139728088, "00000000000000000000000000000000",
            "00d0d4051000000080a4d8a400a520a5"),  # fifth Thunderfury version (no ability grant)
           (736, "d8aa1300",
            "e8aa1300"),  # fifth Thunderfury version (no ability grant)
           (444, "d8aa1300",
            "e8aa1300"),  # fifth Thunderfury version (no ability grant)
           (97831024, "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
            "000000000000403f00000000000000009a801747010000000a000000000000000000000000000000060000000000000000000000000000000000000000000000080000000000803f01000000cdcc4c3e00004041000000000000000000000000010000000000000095f21747010000000f00000000000000000000000000000000000000cdcc4c3d000000000000000095f21747010000000f000000000000000100000000000000010000000000000021cfb846010000000900000000000000"),  # released "thunderfury" option (proc on Auto Shot, no ability grant)
           (97831216, "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
            "4d696c6573746f6e652e20596f757220706574732720626974657320686176652061207b767d25206368616e636520746f206669726520612066726565204d756c74692d53686f742e205468756e646572667572793a2065616368204175746f2053686f742074686174206c616e6473206861732061203525206368616e636520746f20636173742061206672656520436861696e204c696768746e696e672c20736c6f77696e67207768617420697420686974732062792032302520666f72203132207365632e"),  # released "thunderfury" option (proc on Auto Shot, no ability grant)
           (118976856, "a8801747010000000100000000000000",
            "70d4d445010000000300000000000000"),  # released "thunderfury" option (proc on Auto Shot, no ability grant)
           (118976872, "e8801747010000004900000000000000",
            "30d5d44501000000c800000000000000"),  # released "thunderfury" option (proc on Auto Shot, no ability grant)
           (536, "6ec4d405",
            "f8c5d405"),  # released "thunderfury" option (proc on Auto Shot, no ability grant)
           (139728088, "00000000000000000000000000000000",
            "00d0d4051000000080a4d8a400a520a5"),  # released "thunderfury" option (proc on Auto Shot, no ability grant)
           (736, "d8aa1300",
            "e8aa1300"),  # released "thunderfury" option (proc on Auto Shot, no ability grant)
           (444, "d8aa1300",
            "e8aa1300")]  # released "thunderfury" option (proc on Auto Shot, no ability grant)


def _state(d):
    """Patches fully applied to d, or None if d is not the supported build (with any of our edits)."""
    stock = bytearray(d)
    for off, old, new in RETIRED:
        if stock[off:off + len(new) // 2].hex() == new:
            stock[off:off + len(old) // 2] = bytes.fromhex(old)
    have = set()
    for name, edits in PATCHES.items():
        applied = 0
        for off, old, new in edits:
            cur = stock[off:off + len(new) // 2].hex()
            if cur == new:
                stock[off:off + len(old) // 2] = bytes.fromhex(old)
                applied += 1
        if applied == len(edits):
            have.add(name)
    return have if hashlib.sha256(stock).hexdigest() == STOCK_SHA256 else None


def cmd_patch(*args):
    want = [a for a in args if a in PATCHES] or list(PATCHES)
    paths = [a for a in args if a not in PATCHES]
    path = paths[0] if paths else "AzerothSurvivors.exe"
    d = bytearray(open(path, "rb").read())
    have = _state(d)
    if have is None:
        sys.exit("this AzerothSurvivors.exe is a different version than the patches were made for; not touching it")
    todo = [p for p in want if p not in have]
    retired = [(o, old) for o, old, new in RETIRED if d[o:o + len(new) // 2].hex() == new]
    if not todo and not retired:
        return print("already patched: " + ", ".join(DESCRIBE[p] for p in want))
    for off, old in retired:
        d[off:off + len(old) // 2] = bytes.fromhex(old)
    for p in todo:
        for off, old, new in PATCHES[p]:
            d[off:off + len(new) // 2] = bytes.fromhex(new)  # also completes a partly applied older patch
    assert _state(d) == have | set(todo)
    bak = backup(path, "before-patch")
    open(path, "wb").write(d)
    print(f"patched {path}: " + ", ".join(DESCRIBE[p] for p in todo) + f"\nbackup: {bak}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["unlock"]:
        cmd_unlock(*a[1:2])
    elif a[:1] == ["patch"]:
        cmd_patch(*a[1:])
    elif a[:1] == ["decode"] and len(a) == 3:
        open(a[2], "w", encoding="utf-8").write(decode(open(a[1], encoding="utf-8").read()))
    elif a[:1] == ["encode"] and len(a) == 3:
        open(a[2], "w", encoding="utf-8").write(encode(open(a[1], encoding="utf-8").read()))
    else:
        print(__doc__)
