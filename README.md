# מחולל מבזקי חדשות ישראל v2.0

מערכת שאוספת חדשות מ-25+ אתרים ישראליים + 50+ שאילתות Google News, מסווגת עם Claude AI, שומרת ב-Supabase, ומפיקה מבזקים מותאמים.

## מה השתנה מ-v1

| | v1 | v2 |
|---|---|---|
| מקורות | 17 RSS feeds | 25+ RSS + 50+ Google News queries |
| סיווג | מילות מפתח | Claude AI (עם fallback למילות מפתח) |
| אחסון | קובץ Markdown ב-Git | Supabase (PostgreSQL) |
| כפילויות | Jaccard בלבד | duplicate_key מ-AI + Jaccard |
| סיכום | כותרת ארוכה ביותר | Claude כותב מבזק עריכתי |
| קטגוריות | 6 | 14 (כולל חרדי, ערבי, בורסה, טכנולוגיה, משפטי) |
| CLI | ללא פרמטרים | style, hours, categories, max |
| עלות | 0$ | 0$ ללא AI, ~70-95$/חודש עם AI |

## התקנה

### שלב 1: Supabase (אופציונלי אבל מומלץ)

1. צור חשבון ב-[supabase.com](https://supabase.com)
2. צור פרויקט חדש
3. פתח SQL Editor והדבק את ה-SQL מ-`config.py` (חפש `SUPABASE_SCHEMA`)
4. שמור את `Project URL` ו-`anon key` מ-Settings → API

### שלב 2: Claude API (אופציונלי)

1. צור חשבון ב-[console.anthropic.com](https://console.anthropic.com)
2. צור API key
3. טען קרדיט (Haiku לסיווג עולה ~5-15$/חודש)

### שלב 3: GitHub

1. צור repository חדש
2. העלה את הקבצים: `news_analyzer.py`, `config.py`, `requirements.txt`, `.github/workflows/news-analyzer.yml`
3. Settings → Secrets → הוסף:
   - `SUPABASE_URL`
   - `SUPABASE_KEY`
   - `ANTHROPIC_API_KEY`
4. Settings → Actions → Workflow permissions → **Read and write**
5. Actions → הפעל workflow

### בלי Supabase ובלי Claude

המערכת עובדת גם בלעדיהם — פשוט אוספת RSS, מסווגת לפי מילות מפתח, ושומרת מבזק כקובץ. פחות חכם, אבל עובד.

## שימוש

### הרצה מקומית

```bash
pip install -r requirements.txt

# מבזק מלא (איסוף + סיווג + הפקה)
python news_analyzer.py

# סגנון מפורט, 12 שעות, רק ביטחון וכלכלה
python news_analyzer.py --style detailed --hours 12 --categories security economy

# רק איסוף (בלי מבזק)
python news_analyzer.py --collect-only

# מבזק מ-DB (בלי איסוף חדש)
python news_analyzer.py --from-db --hours 48 --style brief
```

### פרמטרים

| פרמטר | ברירת מחדל | אפשרויות |
|--------|-----------|---------|
| `--style` | flash | flash, brief, detailed |
| `--hours` | 24 | 1-144 |
| `--max` | 30 | 1-200 |
| `--categories` | הכל | security, politics, diplomatic, economy, stocks, haredi, arab, health, culture, local, legal, sports, tech, general |
| `--collect-only` | - | איסוף בלבד |
| `--from-db` | - | שליפה מ-DB |
| `--output` | auto | נתיב קובץ |

## מבנה הקבצים

```
├── news_analyzer.py      # מנוע ראשי (~500 שורות)
├── config.py             # הגדרות, מקורות, prompts
├── requirements.txt      # תלויות
├── .github/workflows/
│   └── news-analyzer.yml # GitHub Actions
└── reports/              # מבזקים שנוצרו
```

## עלויות חודשיות

| רכיב | בלי AI | עם AI |
|-------|-------|------|
| GitHub Actions | $0 | $0 |
| Supabase | $0 (free tier) | $0 (free tier) |
| Claude Haiku (סיווג) | - | ~$5-15 |
| Claude Sonnet (מבזקים) | - | ~$10-30 |
| Serper (אופציונלי) | - | ~$50 |
| **סה"כ** | **$0** | **$15-95** |

## בעיות ידועות

- חלק מה-RSS feeds עלולים להפסיק לעבוד כשאתרים משנים URLs
- Google News RSS אינו שירות רשמי ויכול להיחסם
- סיווג מילות מפתח (fallback) פחות מדויק מ-Claude
- אתרים ערביים (פאנט, בוכרא, אלערב) — ה-RSS שלהם לא תמיד יציב
