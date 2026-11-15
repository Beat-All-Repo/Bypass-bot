"""Domain classification: shortener / file host / site / direct / video."""
from urllib.parse import urlsplit

SHORTENERS = [
    "2short.club", "adrinolinks", "adurl.io", "arolinks", "babylinks", "codedew",
    "cryptoinsights", "cuttlinks.com", "cuttty.com", "cuty.io", "cyberloom",
    "droplink.co", "earnlinks.in", "examzculture", "exe.io", "exeygo.com",
    "extralink", "fc-lc.xyz", "fpgo.xyz", "fxlinks", "gadgetsweb", "gadinow.in",
    "gamesmain.xyz", "genas.xyz", "get2short", "go2.pics", "gplinks",
    "greenmountmotors.com", "hblinks", "home.sharclub.in", "indiaearnx",
    "indianshortner", "inshorturl.in", "instantlinks", "inventoryidea",
    "jkdamours.com", "jkssbworld.in", "jobsheel.com", "just2earn.com",
    "katlinks", "kogap.xyz", "leechpro.blog", "linkjust.com", "linkpays.in",
    "links.kmhd.eu", "links.linkshub", "links.modpro", "links.ol-am",
    "links.olamovies", "linkshortify", "linkshub.pro", "liteshort.com", "lksfy",
    "lnbz.la", "loan.kannursalafi.com", "mdiskshort", "nowshort", "odiadance.com",
    "oii.la", "oklink2.online", "ouo.io", "ouo.press", "papajiurl", "psa.wf",
    "publicearn.com", "publicearn.in", "pubnotepad.com", "recruitmentaim.in",
    "rempo.xyz", "sayphotobooth.com", "shikshakdaak", "short4cash.com",
    "shortxlinks", "shrinkme", "softurl", "strictstrategies.com", "techmirror.click",
    "teknoasian", "theindianmirror.in", "tpi.li", "vuotlink.xyz", "v2links",
    "vipshort", "vplink", "vshort", "wildshare.net", "xpshort",
]

GD_HOSTS = [
    "hubcloud", "hubcdn", "hubdrive", "zinkcloud", "tmbcloud", "vcloud", "gcloud.sbs",
    "extraflix", "gdflix", "gdlink", "gdshare", "gd.vifix.site", "drivehub",
    "driveseed", "nexdrive", "dotflix", "dtflix", "fastdlserver", "oxxfile",
    "filepress", "filebee", "10drives.com", "devuploads", "vikingfile", "vik1ngfile",
    "forge-manager-nzxl.onrender.com", "hunter-deploy.onrender.com",
    "secret.dzhq.workers.dev", "devuploads.dzhq.workers.dev",
    "mixologyxbot-token.vercel.app", "aioarea.vercel.app",
    "mrn-bypass-protect-bot-mrn-official.vercel.app",
    "mrn-universe-bypass-protect-bot.vercel.app", "avbypassbot.koyeb.app",
    "mtc1.yolo-school.com", "main.sportswordz.com",
]

SITES = [
    "toonworld4all.me", "archive.toonworld4all.me", "animekaizoku.xyz",
    "anikaizoku.com", "4khdhub", "hdhub4u", "moviesmod", "moviesleech",
    "vegamovies", "skymovieshd", "xdmovies", "katmoviefix", "mkvdrama",
    "katdrama", "dramaday", "pahe.plus", "cinevood", "ziddiflix", "viewcrate",
    "unblockedgames", "1tamilmv",
]

VIDEO = ["youtube.com", "youtu.be", "youtube-nocookie.com"]

DIRECT = ["pixeldrain", "gofile", "akirabox", "transfer.it", "fuckingfast.net",
          "drive.google.com", "drive.usercontent.google.com",
          "drive.olamovies.download", "mega.nz", "mega.co.nz"]


def _hits(host, table):
    return any(entry in host for entry in table)


def classify(url):
    host = urlsplit(url).netloc.lower()
    if not host:
        return None
    if _hits(host, VIDEO):
        return "video"
    if _hits(host, DIRECT):
        return "direct"
    if _hits(host, GD_HOSTS):
        return "host"
    if _hits(host, SITES):
        return "site"
    if _hits(host, SHORTENERS):
        return "short"
    return None