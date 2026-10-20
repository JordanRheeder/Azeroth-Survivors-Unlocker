#!/usr/bin/env python3
"""Azeroth Survivors save unlocker and game patcher.

  python azs_tool.py unlock [SAVE]                   unlock zones, gear, codex, achievements, talent XP
  python azs_tool.py patch  [EXE] [talents] [caches] [bosses]
                                     patch the game (all three if none is named):
                                       talents  talent cap 51 -> 129
                                       caches   battleground caches cost no gold
                                       bosses   big bosses give a legendary treasure
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
#   each pick instead of chaining through every cache picked up at once.
# bosses:  big bosses (Hogger and co.) normally give no treasure. On a boss kill, also queue the
#   bonus treasure guardians give and count it in a "boss treasures" counter (a spare dword at the
#   end of .data). When that treasure is dealt and the counter is set, its rarity-roll luck bonus is
#   1,000,000 instead of 0.25 (weights 60 : 25L : 10L^2 : 4L^3 : L^4), so it is legendary; picking a
#   reward uses the mark up. Guardian and elite treasures roll as before. The new code lives in three
#   int3 padding gaps in .text.
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
               (93450596, "80b9ca09000000", "ebaa0f1f440000")],  # queued: leave it on the ground
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
}
DESCRIBE = {"talents": "talent cap 51 -> 129", "caches": "caches cost no gold",
            "bosses": "big bosses give a legendary treasure"}
STOCK_SHA256 = "3b46bad92e7771afa61c93658fd850937834a40f3671af8b1a3e1d2aeb8b63c7"


def _state(d):
    """Patches fully applied to d, or None if d is not the supported build (with any of our edits)."""
    stock = bytearray(d)
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
    if not todo:
        return print("already patched: " + ", ".join(DESCRIBE[p] for p in want))
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
