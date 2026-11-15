import os

TG_TOKEN = os.getenv("TG_TOKEN", "")

IMPERSONATE_POOL = ["chrome", "chrome124", "chrome120", "chrome110", "safari17_0", "edge101"]
FLARE_URL = os.getenv("FLARE_URL", "").rstrip("/")
PROXY = os.getenv("PROXY", "") or None
COOKIE_FILE = os.getenv("COOKIE_FILE", "cookies.json")

TIMEOUT = int(os.getenv("TIMEOUT", "45"))
RETRIES = int(os.getenv("RETRIES", "4"))
DELAY_MIN = float(os.getenv("DELAY_MIN", "1.0"))
DELAY_MAX = float(os.getenv("DELAY_MAX", "2.5"))

BASE = "https://toonworld4all.me"
ARCHIVE = "https://archive.toonworld4all.me"

MAX_DEPTH = int(os.getenv("MAX_DEPTH", "8"))
SOLVE_SHORTENERS = True          # never trust the shortcut blindly

PAGE_SIZE = int(os.getenv("PAGE_SIZE", "8"))
MAX_CONCURRENT_JOBS = int(os.getenv("MAX_CONCURRENT_JOBS", "3"))
ALLOWED_USERS = {int(x) for x in os.getenv("ALLOWED_USERS", "").replace(" ", "").split(",") if x}

HOST_MIRRORS = {
    "hubcloud": ["hubcloud.pw", "hubcloud.lol", "hubcloud.cx", "hubcloud.foo",
                 "hubcloud.one", "hubcloud.co", "hubcloud.fo", "hubcloud.buzz",
                 "hubcloud.wiki", "hubcloud.dad", "hubcloud.life", "hubcloud.shop"],
    "gdflix": ["gdflix.dev", "new9.gdflix.io", "new8.gdflix.io", "gdflix.io",
               "gdflix.ink", "gdflix.pro", "gdflix.top", "gdflix.cc",
               "gdflix.vip", "gdflix.xyz"],
    "filepress": [f"new{n}.filepress.{t}" for n in range(1, 10) for t in ("lat", "wiki")],
}

QUALITY_MAP = [(r"2160p|4k|uhd", "2160p"), (r"1080p|fhd", "1080p"),
               (r"720p", "720p"), (r"480p|bluray", "480p"), (r"360p", "360p")]

SUPPORTED_SITES = [
    "10drives.com", "1tamilmv", "2short.club", "4khdhub", "adrinolinks", "adurl.io",
    "aioarea.vercel.app", "akirabox", "anikaizoku.com/redirect/",
    "animekaizoku.xyz/redirect/", "archive.toonworld4all.me", "arolinks",
    "avbypassbot.koyeb.app", "babylinks", "cinevood", "codedew", "cryptoinsights",
    "cuttlinks.com", "cuttty.com", "cuty.io", "cyberloom", "devuploads.com",
    "devuploads.dzhq.workers.dev", "dotflix", "dramaday", "drive.google.com",
    "drive.olamovies.download", "drive.usercontent.google.com", "drivehub",
    "driveseed", "droplink.co", "dtflix", "earnlinks.in", "episodes.linkshub",
    "episodes.modpro", "examzculture", "exe.io", "exeygo.com", "extraflix",
    "extralink", "fastdlserver", "fc-lc.xyz", "filebee", "filepress",
    "forge-manager-nzxl.onrender.com", "fpgo.xyz", "fuckingfast.net", "fxlinks",
    "gadgetsweb", "gadinow.in", "gamesmain.xyz", "gcloud.sbs", "gd.vifix.site",
    "gdflix", "gdlink", "gdshare", "genas.xyz", "get2short", "go2.pics/go2?id=",
    "gofile", "gplinks", "greenmountmotors.com", "hblinks", "hdhub4u",
    "home.sharclub.in", "hubcdn", "hubcloud", "hubdrive",
    "hunter-deploy.onrender.com", "indiaearnx", "indianshortner", "inshorturl.in",
    "instantlinks", "inventoryidea", "jkdamours.com", "jkssbworld.in", "jobsheel.com",
    "just2earn.com", "katdrama", "katlinks", "katmoviefix", "kogap.xyz",
    "leechpro.blog", "link.xdmovies", "linkjust.com", "linkpays.in", "links.kmhd.eu",
    "links.linkshub", "links.modpro", "links.ol-am", "links.olamovies",
    "links.toonworld4all.me/redirect", "linkshortify", "linkshub.pro",
    "liteshort.com", "lksfy", "lnbz.la", "loan.kannursalafi.com", "m.youtube.com",
    "main.sportswordz.com", "mdiskshort", "mixologyxbot-token.vercel.app",
    "mkvdrama.net", "moviesleech", "moviesmod",
    "mrn-bypass-protect-bot-mrn-official.vercel.app",
    "mrn-universe-bypass-protect-bot.vercel.app", "mtc1.yolo-school.com",
    "music.youtube.com", "nexdrive", "nowshort", "odiadance.com", "oii.la",
    "oklink2.online", "ouo.io", "ouo.press", "oxxfile", "pahe.plus", "papajiurl",
    "pixeldrain", "posts.modpro", "psa.wf/goto", "publicearn.com", "publicearn.in",
    "pubnotepad.com", "recruitmentaim.in", "rempo.xyz", "sayphotobooth.com",
    "secret.dzhq.workers.dev", "shikshakdaak", "short4cash.com", "shortxlinks",
    "shrinkme", "skymovieshd", "softurl", "strictstrategies.com", "techmirror.click",
    "teknoasian", "theindianmirror.in", "tmbcloud", "toonworld4all.me",
    "toonworld4all.me/redirect/", "tpi.li", "transfer.it", "unblockedgames",
    "v2links", "vcloud", "vegamovies", "viewcrate", "vik1ngfile", "vikingfile",
    "vipshort", "vplink", "vshort", "vuotlink.xyz", "wildshare.net", "xdmovies",
    "xpshort", "youtu.be", "youtube-nocookie.com", "youtube.com", "ziddiflix",
    "zinkcloud",
]