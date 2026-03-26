# -*- coding: utf-8 -*-
"""
הגדרות מערכת מבזקי חדשות ישראל — גרסה 2.0
כולל: RSS ישיר, Google News RSS, Supabase, Claude API
"""

import os

# ============================================================
# 🔑 API Keys & Database
# ============================================================
# הגדר כ-environment variables (או כ-GitHub Secrets)
SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')

# ============================================================
# 📡 RSS Feeds ישירים — 30+ מקורות
# ============================================================
RSS_FEEDS = {
    # ── חדשות כלליות ──
    'ynet': {
        'url': 'https://www.ynet.co.il/Integration/StoryRss2.xml',
        'name': 'Ynet',
        'sector': 'mainstream',
        'language': 'he'
    },
    'walla': {
        'url': 'https://rss.walla.co.il/feed/1?type=main',
        'name': 'וואלה',
        'sector': 'mainstream',
        'language': 'he'
    },
    'mako': {
        'url': 'https://www.mako.co.il/RSS/rss-news.xml',
        'name': 'Mako',
        'sector': 'mainstream',
        'language': 'he'
    },
    'kan': {
        'url': 'https://www.kan.org.il/content/kan/rss/news.xml',
        'name': 'כאן 11',
        'sector': 'mainstream',
        'language': 'he'
    },
    'israelhayom': {
        'url': 'https://www.israelhayom.co.il/rss/news',
        'name': 'ישראל היום',
        'sector': 'mainstream',
        'language': 'he'
    },
    'maariv': {
        'url': 'https://www.maariv.co.il/Rss/RssFeedsLive',
        'name': 'מעריב',
        'sector': 'mainstream',
        'language': 'he'
    },
    'haaretz': {
        'url': 'https://www.haaretz.co.il/cmlink/1.1617469',
        'name': 'הארץ',
        'sector': 'mainstream',
        'language': 'he'
    },
    'channel14': {
        'url': 'https://www.now14.co.il/feed/',
        'name': 'ערוץ 14',
        'sector': 'mainstream',
        'language': 'he'
    },
    'i24': {
        'url': 'https://www.i24news.tv/he/rss',
        'name': 'i24',
        'sector': 'mainstream',
        'language': 'he'
    },

    # ── כלכלה ──
    'globes': {
        'url': 'https://www.globes.co.il/webservice/rss/rssfeeder.asmx/FeederNode?iID=1725',
        'name': 'גלובס',
        'sector': 'economy',
        'language': 'he'
    },
    'calcalist': {
        'url': 'https://www.calcalist.co.il/GeneralRSS/0,16335,L-8,00.xml',
        'name': 'כלכליסט',
        'sector': 'economy',
        'language': 'he'
    },
    'themarker': {
        'url': 'https://www.themarker.com/cmlink/1.1617470',
        'name': 'TheMarker',
        'sector': 'economy',
        'language': 'he'
    },

    # ── חרדי / דתי ──
    'kikar': {
        'url': 'https://www.kikar.co.il/rss',
        'name': 'כיכר השבת',
        'sector': 'haredi',
        'language': 'he'
    },
    'bhol': {
        'url': 'https://www.bhol.co.il/rss.aspx',
        'name': 'בחדרי חרדים',
        'sector': 'haredi',
        'language': 'he'
    },
    'kipa': {
        'url': 'https://www.kipa.co.il/rss/main.xml',
        'name': 'כיפה',
        'sector': 'religious',
        'language': 'he'
    },
    'hamodia': {
        'url': 'https://www.hamodia.co.il/feed/',
        'name': 'המודיע',
        'sector': 'haredi',
        'language': 'he'
    },

    # ── ערבי ──
    'panet': {
        'url': 'https://www.panet.co.il/rss',
        'name': 'פאנט',
        'sector': 'arab',
        'language': 'ar'
    },
    'bokra': {
        'url': 'https://www.bokra.net/rss',
        'name': 'بُكرا',
        'sector': 'arab',
        'language': 'ar'
    },
    'alarab': {
        'url': 'https://www.alarab.com/rss',
        'name': 'العرب',
        'sector': 'arab',
        'language': 'ar'
    },

    # ── ספורט ──
    'ynet_sport': {
        'url': 'https://www.ynet.co.il/Integration/StoryRss3.xml',
        'name': 'Ynet ספורט',
        'sector': 'sport',
        'language': 'he'
    },
    'sport5': {
        'url': 'https://www.sport5.co.il/rss/RSS_Sport.xml',
        'name': 'ספורט 5',
        'sector': 'sport',
        'language': 'he'
    },
    'one': {
        'url': 'https://www.one.co.il/RSS/rss.xml',
        'name': 'One',
        'sector': 'sport',
        'language': 'he'
    },

    # ── טכנולוגיה ──
    'geektime': {
        'url': 'https://www.geektime.co.il/feed/',
        'name': 'גיקטיים',
        'sector': 'tech',
        'language': 'he'
    },

    # ── מקומי ──
    'haifa': {
        'url': 'https://www.haifahahadasha.co.il/feed/',
        'name': 'חיפה החדשה',
        'sector': 'local',
        'language': 'he'
    },
    'mynet_tlv': {
        'url': 'https://www.mynet.co.il/Ext/Comp/ArticleLayout/CdaArticlePrint498/1,2506,L-498,00.xml',
        'name': 'mynet תל אביב',
        'sector': 'local',
        'language': 'he'
    },
}

# ============================================================
# 🔍 Google News RSS — שאילתות לפי קטגוריה
# ============================================================
# פורמט URL: https://news.google.com/rss/search?q={query}&hl=he&gl=IL&ceid=IL:he

GOOGLE_NEWS_BASE = 'https://news.google.com/rss/search?q={query}&hl={lang}&gl=IL&ceid=IL:{lang}'

GOOGLE_NEWS_QUERIES = {
    # ── כללי ──
    'general': {
        'queries': [
            'חדשות ישראל',
            'ממשלת ישראל',
            'כנסת',
        ],
        'language': 'he'
    },

    # ── ביטחוני ──
    'security': {
        'queries': [
            'צהל',
            'ביטחון ישראל',
            'עזה',
            'חיזבאללה לבנון',
            'איראן גרעין',
            'פיגוע ישראל',
            'טילים רקטות ישראל',
            'שבכ שינבית',
            'חטופים',
        ],
        'language': 'he'
    },

    # ── פוליטיקה ──
    'politics': {
        'queries': [
            'כנסת חוק הצבעה',
            'נתניהו',
            'קואליציה אופוזיציה',
            'בגץ בית משפט עליון',
            'בחירות ישראל',
        ],
        'language': 'he'
    },

    # ── כלכלה ──
    'economy': {
        'queries': [
            'כלכלה ישראל',
            'בנק ישראל ריבית',
            'נדלן מחירי דירות ישראל',
            'יוקר מחיה ישראל',
            'סטארטאפ הייטק ישראל',
        ],
        'language': 'he'
    },

    # ── בורסה ──
    'stocks': {
        'queries': [
            'בורסה תל אביב',
            'שער דולר שקל',
            'מדד תא 35',
        ],
        'language': 'he'
    },

    # ── חרדי ──
    'haredi': {
        'queries': [
            'חרדים',
            'גיוס חרדים',
            'ישיבות כוללים',
            'רבנים פסיקה',
        ],
        'language': 'he'
    },

    # ── ערבי (עברית) ──
    'arab_he': {
        'queries': [
            'ערביי ישראל',
            'חברה ערבית ישראל',
        ],
        'language': 'he'
    },

    # ── ערבי (ערבית) ──
    'arab_ar': {
        'queries': [
            'رسائل عرب إسرائيل',
            'مجتمع عربي إسرائيل',
        ],
        'language': 'ar'
    },

    # ── בריאות ──
    'health': {
        'queries': [
            'בריאות ישראל',
            'משרד הבריאות',
            'בית חולים ישראל',
            'קופת חולים',
        ],
        'language': 'he'
    },

    # ── תרבות ──
    'culture': {
        'queries': [
            'תרבות ישראל',
            'קולנוע ישראלי',
            'פסטיבל ישראל',
            'מוזיקה ישראלית',
        ],
        'language': 'he'
    },

    # ── מקומי ──
    'local': {
        'queries': [
            'עיריית תל אביב',
            'עיריית ירושלים',
            'עיריית חיפה',
            'עיריית באר שבע',
            'פריפריה נגב גליל',
        ],
        'language': 'he'
    },

    # ── משפטי ──
    'legal': {
        'queries': [
            'בגץ פסיקה',
            'משפט פלילי ישראל',
            'פרקליטות ישראל',
        ],
        'language': 'he'
    },

    # ── ספורט ──
    'sports': {
        'queries': [
            'כדורגל ישראלי',
            'נבחרת ישראל',
            'מכבי הפועל',
        ],
        'language': 'he'
    },

    # ── טכנולוגיה ──
    'tech': {
        'queries': [
            'הייטק ישראלי',
            'סייבר ישראל',
            'בינה מלאכותית ישראל',
        ],
        'language': 'he'
    },
}

# ============================================================
# 🤖 Claude API — הגדרות סיווג
# ============================================================

CLASSIFICATION_MODEL = 'claude-haiku-4-5-20251001'  # זול ומהיר לסיווג
BULLETIN_MODEL = 'claude-sonnet-4-20250514'  # איכותי להפקת מבזקים

BULLETIN_PROMPT = """אתה עורך חדשות ישראלי מנוסה. הפק מבזק חדשותי מהידיעות הבאות.

הגדרות:
- סגנון: {style}
- מקסימום ידיעות: {max_items}
- קטגוריות: {categories}
- טווח זמן: {hours} שעות אחרונות

כללי סגנון:
- flash: שורה אחת לידיעה, עד 15 מילים, ללא פרשנות
- brief: 2-3 משפטים לידיעה, כולל הקשר בסיסי
- detailed: פסקה לידיעה, כולל רקע והשלכות

כללי עריכה:
- סדר לפי חשיבות (ידיעות עם הרבה מקורות קודם)
- אחד כפילויות — כמה מקורות לאותו סיפור = ידיעה אחת
- ציין מקורות בסוגריים
- שפה עיתונאית, ניטרלית, ללא הטיה
- בעברית
- אל תוסיף מידע שלא מופיע בידיעות

הידיעות:
{news_items}"""

# ============================================================
# ⚙️ הגדרות כלליות
# ============================================================
MIN_TITLE_LENGTH = 10
MAX_NEWS_AGE_HOURS = 24  # ברירת מחדל לאיסוף
SIMILARITY_THRESHOLD = 0.55  # סף דמיון Jaccard (הורד מ-0.6)
MAX_ITEMS_PER_BULLETIN = 50
RSS_FETCH_TIMEOUT = 15  # שניות
GOOGLE_NEWS_FETCH_TIMEOUT = 20
MAX_CONCURRENT_FEEDS = 8
BATCH_SIZE_FOR_CLASSIFICATION = 10  # כמה ידיעות לשלוח ל-Claude בבת אחת

# מילות מפתח לזיהוי "בלעדי" (×3 ניקוד)
EXCLUSIVE_KEYWORDS = [
    'פרסום ראשון', 'בלעדי', 'בלעדי:', 'בלעדי ל',
    'נחשף לראשונה', 'חושף:', 'נודע ל', 'התגלה כי',
]

# ============================================================
# 🗄️ Supabase — מבנה טבלאות (SQL להרצה ידנית)
# ============================================================
SUPABASE_SCHEMA = """
-- הרץ את ה-SQL הזה ב-Supabase SQL Editor פעם אחת

-- טבלת ידיעות
CREATE TABLE IF NOT EXISTS news_items (
    id BIGSERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    summary TEXT,
    url TEXT NOT NULL,
    url_hash TEXT UNIQUE NOT NULL,
    source_name TEXT NOT NULL,
    source_sector TEXT,
    language TEXT DEFAULT 'he',
    category TEXT,
    keywords TEXT[],
    importance TEXT DEFAULT 'medium',
    duplicate_key TEXT,
    is_exclusive BOOLEAN DEFAULT FALSE,
    score INTEGER DEFAULT 10,
    published_at TIMESTAMPTZ,
    collected_at TIMESTAMPTZ DEFAULT NOW(),
    classified BOOLEAN DEFAULT FALSE
);

-- אינדקסים לביצועים
CREATE INDEX IF NOT EXISTS idx_news_published ON news_items(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_news_category ON news_items(category);
CREATE INDEX IF NOT EXISTS idx_news_collected ON news_items(collected_at DESC);
CREATE INDEX IF NOT EXISTS idx_news_url_hash ON news_items(url_hash);
CREATE INDEX IF NOT EXISTS idx_news_duplicate_key ON news_items(duplicate_key);

-- טבלת לוג ריצות
CREATE TABLE IF NOT EXISTS collection_runs (
    id BIGSERIAL PRIMARY KEY,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    items_collected INTEGER DEFAULT 0,
    items_classified INTEGER DEFAULT 0,
    sources_succeeded INTEGER DEFAULT 0,
    sources_failed INTEGER DEFAULT 0,
    errors TEXT[]
);
"""
