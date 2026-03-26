# -*- coding: utf-8 -*-
"""
מנוע מבזקי חדשות ישראל — גרסה 2.0
- איסוף מ-30+ RSS feeds ישירים + 50+ שאילתות Google News
- שמירה ב-Supabase (PostgreSQL)
- סיווג עם Claude API (Haiku)
- הפקת מבזקים עם Claude API (Sonnet)
"""

import feedparser
import hashlib
import json
import re
import requests as http_requests
import sys
import time
import traceback
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote_plus

import config

# ============================================================
# אתחול שירותים חיצוניים (אופציונלי — עובד גם בלעדיהם)
# ============================================================

# Supabase
_supabase_client = None
def get_supabase():
    global _supabase_client
    if _supabase_client is None and config.SUPABASE_URL and config.SUPABASE_KEY:
        try:
            from supabase import create_client
            _supabase_client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
            print("✅ Supabase מחובר")
        except Exception as e:
            print(f"⚠️  Supabase לא זמין: {e}")
    return _supabase_client

# Anthropic
_anthropic_client = None
def get_anthropic():
    global _anthropic_client
    if _anthropic_client is None and config.ANTHROPIC_API_KEY:
        try:
            from anthropic import Anthropic
            _anthropic_client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
            print("✅ Claude API מחובר")
        except Exception as e:
            print(f"⚠️  Claude API לא זמין: {e}")
    return _anthropic_client


# ============================================================
# Class: NewsCollector — איסוף מכל המקורות
# ============================================================

class NewsCollector:
    """אוסף ידיעות מ-RSS ישיר ומ-Google News RSS"""

    def __init__(self):
        self.articles: List[Dict] = []
        self.errors: List[str] = []
        self.sources_ok = 0
        self.sources_fail = 0

    def collect_all(self) -> List[Dict]:
        """איסוף מכל המקורות — RSS ישיר + Google News"""
        print("=" * 60)
        print("📡 שלב 1: איסוף חדשות")
        print("=" * 60)

        # 1) RSS ישיר
        print(f"\n── RSS ישיר ({len(config.RSS_FEEDS)} מקורות) ──")
        self._collect_direct_rss()

        # 2) Google News RSS
        total_queries = sum(len(c['queries']) for c in config.GOOGLE_NEWS_QUERIES.values())
        print(f"\n── Google News RSS ({total_queries} שאילתות) ──")
        self._collect_google_news()

        # 3) ניקוי כפילויות לפי URL
        before = len(self.articles)
        self._deduplicate_by_url()
        after = len(self.articles)

        print(f"\n📊 סיכום איסוף:")
        print(f"   נאספו: {before} ידיעות")
        print(f"   אחרי הסרת כפילויות URL: {after}")
        print(f"   מקורות תקינים: {self.sources_ok}")
        print(f"   מקורות שנכשלו: {self.sources_fail}")
        if self.errors:
            print(f"   שגיאות: {len(self.errors)}")

        return self.articles

    # מיפוי שמות מקורות — לנקות domain names שגוגל מחזיר
    SOURCE_NAME_MAP = {
        'news.walla.co.il': 'וואלה',
        'www.walla.co.il': 'וואלה',
        'walla.co.il': 'וואלה',
        'www.ynet.co.il': 'Ynet',
        'ynet.co.il': 'Ynet',
        'ynet': 'Ynet',
        'www.mako.co.il': 'Mako',
        'www.kan.org.il': 'כאן 11',
        'www.israelhayom.co.il': 'ישראל היום',
        'www.maariv.co.il': 'מעריב',
        'www.haaretz.co.il': 'הארץ',
        'www.now14.co.il': 'ערוץ 14',
        'www.i24news.tv': 'i24',
        'i24NEWS': 'i24',
        'www.globes.co.il': 'גלובס',
        'www.calcalist.co.il': 'כלכליסט',
        'Calcalist': 'כלכליסט',
        'www.themarker.com': 'TheMarker',
        'www.kikar.co.il': 'כיכר השבת',
        'www.bhol.co.il': 'בחדרי חרדים',
        'www.kipa.co.il': 'כיפה',
        'www.sport5.co.il': 'ספורט 5',
        'www.geektime.co.il': 'גיקטיים',
        'סרוגים': 'סרוגים',
        'המחדש': 'המחדש',
        'מקור ראשון': 'מקור ראשון',
        'היום': 'ישראל היום',
    }

    def _normalize_source_name(self, name: str) -> str:
        """ניקוי שם מקור — המרת domains לשמות קריאים"""
        return self.SOURCE_NAME_MAP.get(name, name)

    def _fetch_feed(self, url: str, timeout: int = 15) -> feedparser.FeedParserDict:
        """שליפת RSS עם timeout"""
        try:
            resp = http_requests.get(
                url,
                timeout=timeout,
                headers={'User-Agent': 'Mozilla/5.0 NewsBot/2.0'}
            )
            resp.raise_for_status()
            return feedparser.parse(resp.content)
        except http_requests.Timeout:
            raise TimeoutError(f"timeout after {timeout}s")
        except http_requests.RequestException as e:
            raise ConnectionError(str(e))

    def _collect_direct_rss(self):
        """איסוף מ-RSS feeds ישירים במקביל"""
        def fetch_one(feed_id, feed_info):
            try:
                feed = self._fetch_feed(
                    feed_info['url'],
                    timeout=config.RSS_FETCH_TIMEOUT,
                )
                items = []
                for entry in feed.entries:
                    article = self._parse_entry(entry, feed_info)
                    if article:
                        items.append(article)
                return feed_info['name'], items, None
            except Exception as e:
                return feed_info['name'], [], str(e)

        with ThreadPoolExecutor(max_workers=config.MAX_CONCURRENT_FEEDS) as executor:
            futures = {
                executor.submit(fetch_one, fid, finfo): fid
                for fid, finfo in config.RSS_FEEDS.items()
            }
            for future in as_completed(futures):
                name, items, error = future.result()
                if error:
                    print(f"  ✗ {name}: {error}")
                    self.sources_fail += 1
                    self.errors.append(f"RSS {name}: {error}")
                else:
                    print(f"  ✓ {name}: {len(items)} ידיעות")
                    self.articles.extend(items)
                    self.sources_ok += 1

    def _collect_google_news(self):
        """איסוף מ-Google News RSS לפי שאילתות מוגדרות"""
        def fetch_query(category, query, language):
            url = config.GOOGLE_NEWS_BASE.format(
                query=quote_plus(query),
                lang=language
            )
            try:
                feed = self._fetch_feed(
                    url,
                    timeout=config.GOOGLE_NEWS_FETCH_TIMEOUT,
                )
                items = []
                for entry in feed.entries:
                    # Google News מחזיר מקור אמיתי בתוך source tag
                    source_name = 'Google News'
                    if hasattr(entry, 'source') and hasattr(entry.source, 'title'):
                        source_name = entry.source.title

                    fake_feed_info = {
                        'name': source_name,
                        'sector': category,
                        'language': language,
                    }
                    article = self._parse_entry(entry, fake_feed_info)
                    if article:
                        article['via_google_news'] = True
                        article['google_query'] = query
                        items.append(article)
                return query, items, None
            except Exception as e:
                return query, [], str(e)

        all_queries = []
        for category, cat_config in config.GOOGLE_NEWS_QUERIES.items():
            for q in cat_config['queries']:
                all_queries.append((category, q, cat_config['language']))

        with ThreadPoolExecutor(max_workers=config.MAX_CONCURRENT_FEEDS) as executor:
            futures = {
                executor.submit(fetch_query, cat, q, lang): q
                for cat, q, lang in all_queries
            }
            for future in as_completed(futures):
                query, items, error = future.result()
                if error:
                    self.errors.append(f"GNews '{query}': {error}")
                    self.sources_fail += 1
                else:
                    if items:
                        print(f"  ✓ \"{query}\": {len(items)} ידיעות")
                    self.sources_ok += 1
                    self.articles.extend(items)

    def _parse_entry(self, entry, feed_info: Dict) -> Optional[Dict]:
        """ממיר entry בודד מ-RSS למבנה אחיד"""
        title = (entry.get('title') or '').strip()
        if len(title) < config.MIN_TITLE_LENGTH:
            return None

        url = (entry.get('link') or '').strip()
        if not url:
            return None

        summary = (entry.get('summary') or entry.get('description') or '').strip()
        # נקה HTML tags מהתקציר
        summary = re.sub(r'<[^>]+>', '', summary).strip()
        # חתוך תקצירים ארוכים מדי
        if len(summary) > 500:
            summary = summary[:497] + '...'

        published = self._parse_date(entry)

        # סנן ידיעות ישנות מדי
        cutoff = datetime.now(timezone.utc) - timedelta(hours=config.MAX_NEWS_AGE_HOURS)
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        if published < cutoff:
            return None

        # זיהוי בלעדי
        combined_text = f"{title} {summary}".lower()
        is_exclusive = any(kw.lower() in combined_text for kw in config.EXCLUSIVE_KEYWORDS)

        url_hash = hashlib.md5(url.encode()).hexdigest()
        source_name = self._normalize_source_name(feed_info['name'])

        return {
            'title': title,
            'summary': summary,
            'url': url,
            'url_hash': url_hash,
            'source_name': source_name,
            'source_sector': feed_info.get('sector', 'unknown'),
            'language': feed_info.get('language', 'he'),
            'published_at': published.isoformat(),
            'is_exclusive': is_exclusive,
            'score': 30 if is_exclusive else 10,
            'category': None,
            'keywords': [],
            'importance': 'medium',
            'duplicate_key': None,
            'classified': False,
            'via_google_news': False,
            'google_query': None,
        }

    def _parse_date(self, entry) -> datetime:
        """פענוח תאריך מ-RSS entry"""
        for attr in ('published_parsed', 'updated_parsed'):
            parsed = getattr(entry, attr, None)
            if parsed:
                try:
                    return datetime(*parsed[:6], tzinfo=timezone.utc)
                except Exception:
                    pass
        return datetime.now(timezone.utc)

    def _deduplicate_by_url(self):
        """הסרת כפילויות לפי URL hash"""
        seen = set()
        unique = []
        for a in self.articles:
            if a['url_hash'] not in seen:
                seen.add(a['url_hash'])
                unique.append(a)
        self.articles = unique


# ============================================================
# Class: NewsClassifier — סיווג עם Claude API (או fallback)
# ============================================================

class NewsClassifier:
    """מסווג ידיעות — Claude API אם זמין, אחרת מילות מפתח"""

    # מילות מפתח כ-fallback (מורחב מהגרסה הקודמת)
    KEYWORD_MAP = {
        'security': [
            'צה"ל', 'צהל', 'חמאס', 'חיזבאללה', 'עזה', 'לבנון', 'גבול',
            'טיל', 'טילים', 'רקטה', 'תקיפה', 'פיגוע', 'טרור', 'חטוף',
            'חטופים', 'מבצע', 'חייל', 'מילואים', 'איראן', 'סוריה',
            'תימן', 'חותים', 'אזעקה', 'יירוט', 'כיפת ברזל', 'צבא',
            'שבכ', 'מוסד', 'שינבית', 'גדר', 'מנהרה', 'חדירה',
        ],
        'politics': [
            'ממשלה', 'כנסת', 'ח"כ', 'נתניהו', 'קואליציה', 'אופוזיציה',
            'מפלגה', 'ליכוד', 'יש עתיד', 'הצבעה', 'הצעת חוק', 'חקיקה',
            'בן גביר', 'סמוטריץ', 'לפיד', 'גנץ',
        ],
        'diplomatic': [
            'ארה"ב', 'בית הלבן', 'טראמפ', 'שגריר', 'דיפלומטי', 'הסכם',
            'שר החוץ', 'האו"ם', 'מועצת הביטחון', 'נאט"ו', 'נורמליזציה',
            'מצרים', 'ירדן', 'סעודיה', 'אמירויות',
        ],
        'economy': [
            'בנק ישראל', 'ריבית', 'משכנתא', 'אינפלציה', 'תקציב',
            'מע"מ', 'מס הכנסה', 'הסתדרות', 'שביתה', 'יוקר המחיה', 'מחירים',
            'סטארטאפ', 'גיוס הון', 'השקעה',
        ],
        'stocks': [
            'בורסה', 'מניות', 'מדד', 'תא 35', 'דולר', 'שקל', 'שער',
            'וול סטריט', 'נאסדק', 'ביטקוין', 'קריפטו',
        ],
        'haredi': [
            'חרדי', 'חרדים', 'ישיבה', 'ישיבות', 'כולל', 'הרב',
            'אדמו"ר', 'תורה', 'גיוס חרדים', 'שבת', 'כשרות', 'בית דין',
            'אגודת ישראל', 'דגל התורה', 'ש"ס',
        ],
        'arab': [
            'ערבי', 'ערבים', 'ערביי', 'בדואי', 'בדואים', 'נגב',
            'משולש', 'דרוזי', 'דרוזים', 'رئيس', 'عرب',
        ],
        'health': [
            'בריאות', 'בית חולים', 'רופא', 'מטופל', 'תרופה', 'חיסון',
            'קופת חולים', 'מכבי', 'כללית', 'לאומית', 'מאוחדת',
        ],
        'culture': [
            'פסטיבל', 'תיאטרון', 'קולנוע', 'סרט', 'מוזיקה', 'זמר',
            'אמן', 'תערוכה', 'מוזיאון', 'ספר', 'סופר', 'פרס ישראל',
        ],
        'local': [
            'עירייה', 'עיריית', 'ראש עיר', 'מועצה מקומית', 'מועצה אזורית',
            'תושבים', 'שכונה', 'תחבורה ציבורית', 'רכבת קלה',
        ],
        'legal': [
            'בגץ', 'בג"ץ', 'בית משפט', 'שופט', 'פרקליטות', 'משפט',
            'עורך דין', 'תביעה', 'עתירה', 'פסק דין',
        ],
        'sports': [
            'נבחרת', 'גביע', 'אליפות', 'ליגה', 'מכבי', 'הפועל', 'בית"ר',
            'כדורגל', 'כדורסל', 'אולימפי', 'יורוליג', 'מאמן',
        ],
        'tech': [
            'הייטק', 'סייבר', 'בינה מלאכותית', 'AI', 'אפליקציה',
            'טכנולוגיה', 'חדשנות', 'רובוט',
        ],
    }

    # מיפוי sector → category (כי השמות לא תמיד תואמים)
    SECTOR_TO_CATEGORY = {
        'mainstream': 'general',
        'religious': 'haredi',
        'sport': 'sports',
        'economy': 'economy',
        'haredi': 'haredi',
        'arab': 'arab',
        'tech': 'tech',
        'local': 'local',
    }

    def classify_all(self, articles: List[Dict]) -> List[Dict]:
        """סיווג כל הידיעות — Claude אם זמין, אחרת fallback"""
        print("\n" + "=" * 60)
        print("🏷️  שלב 2: סיווג ידיעות")
        print("=" * 60)

        client = get_anthropic()

        if client:
            print(f"  משתמש ב-Claude API ({config.CLASSIFICATION_MODEL})")
            return self._classify_with_claude(articles, client)
        else:
            print("  משתמש ב-fallback (מילות מפתח)")
            return self._classify_with_keywords(articles)

    def _classify_with_claude(self, articles: List[Dict], client) -> List[Dict]:
        """סיווג באצוות עם Claude API"""
        unclassified = [a for a in articles if not a['classified']]
        total = len(unclassified)
        classified_count = 0
        batch_size = config.BATCH_SIZE_FOR_CLASSIFICATION

        for i in range(0, total, batch_size):
            batch = unclassified[i:i + batch_size]

            # בנה prompt אחד לכל הבאצ'
            items_text = ""
            for j, a in enumerate(batch):
                items_text += f"\n--- ידיעה {j+1} ---\n"
                items_text += f"כותרת: {a['title']}\n"
                items_text += f"תקציר: {a['summary'][:200]}\n"
                items_text += f"מקור: {a['source_name']}\n"

            prompt = f"""סווג את כל הידיעות הבאות. החזר JSON array בלבד (ללא markdown, ללא הסברים).
כל אלמנט במערך צריך להכיל:
- "category": אחת מ: general, security, politics, diplomatic, economy, stocks, haredi, arab, health, culture, local, legal, sports, tech
- "keywords": מערך של עד 5 מילות מפתח בעברית
- "importance": high/medium/low
- "duplicate_key": ביטוי של 3-5 מילים שמתאר את הסיפור

{items_text}

החזר JSON array עם {len(batch)} אלמנטים בדיוק, לפי הסדר."""

            try:
                response = client.messages.create(
                    model=config.CLASSIFICATION_MODEL,
                    max_tokens=2000,
                    messages=[{"role": "user", "content": prompt}]
                )
                text = response.content[0].text.strip()
                # נקה markdown code blocks אם יש
                text = re.sub(r'^```json\s*', '', text)
                text = re.sub(r'\s*```$', '', text)

                results = json.loads(text)

                for j, a in enumerate(batch):
                    if j < len(results):
                        r = results[j]
                        a['category'] = r.get('category', 'general')
                        a['keywords'] = r.get('keywords', [])
                        a['importance'] = r.get('importance', 'medium')
                        a['duplicate_key'] = r.get('duplicate_key', '')
                        a['classified'] = True
                        classified_count += 1

            except json.JSONDecodeError:
                print(f"  ⚠️  שגיאת JSON בבאצ' {i//batch_size + 1}, עובר ל-fallback")
                for a in batch:
                    self._classify_single_keyword(a)
                    classified_count += 1
            except Exception as e:
                print(f"  ⚠️  שגיאת API בבאצ' {i//batch_size + 1}: {e}")
                for a in batch:
                    self._classify_single_keyword(a)
                    classified_count += 1

            # rate limiting
            time.sleep(0.5)

        print(f"  סווגו {classified_count}/{total} ידיעות")

        # סטטיסטיקות
        self._print_category_stats(articles)
        return articles

    def _classify_with_keywords(self, articles: List[Dict]) -> List[Dict]:
        """סיווג לפי מילות מפתח (fallback)"""
        for a in articles:
            self._classify_single_keyword(a)
        self._print_category_stats(articles)
        return articles

    def _classify_single_keyword(self, article: Dict):
        """סיווג ידיעה בודדת לפי מילות מפתח"""
        text = f"{article['title']} {article['summary']}".lower()
        scores = {}
        for cat, keywords in self.KEYWORD_MAP.items():
            score = sum(1 for kw in keywords if kw.lower() in text)
            if score > 0:
                scores[cat] = score

        # קטגוריה מ-sector של המקור כ-hint
        sector = self.SECTOR_TO_CATEGORY.get(article.get('source_sector', ''), '')
        if sector in scores:
            scores[sector] += 2  # בונוס למגזר המקור

        if scores:
            article['category'] = max(scores, key=scores.get)
        else:
            article['category'] = 'general'

        article['classified'] = True
        article['duplicate_key'] = ' '.join(article['title'].split()[:5])

    def _print_category_stats(self, articles: List[Dict]):
        """הדפסת סטטיסטיקות סיווג"""
        counts = Counter(a['category'] for a in articles)
        print("\n  התפלגות קטגוריות:")
        for cat, count in counts.most_common():
            print(f"    {cat}: {count}")


# ============================================================
# Class: TopicMerger — איחוד כפילויות
# ============================================================

class TopicMerger:
    """מאחד ידיעות דומות ומדרג לפי חשיבות"""

    def merge_and_rank(self, articles: List[Dict]) -> List[Dict]:
        """מאחד כפילויות ומדרג"""
        print("\n" + "=" * 60)
        print("🔄 שלב 3: איחוד וניקוד")
        print("=" * 60)

        # קיבוץ לפי duplicate_key דומה
        topics = self._group_by_similarity(articles)

        # חישוב ניקוד לכל topic
        scored = []
        for key, group in topics.items():
            sources = list(set(a['source_name'] for a in group))
            num_sources = len(sources)
            has_exclusive = any(a['is_exclusive'] for a in group)

            # ניקוד: מקורות × 10, בלעדי × 3
            score = num_sources * 10
            if has_exclusive:
                score = max(score, 30) + (num_sources - 1) * 10

            # importance boost
            if any(a.get('importance') == 'high' for a in group):
                score += 15

            # בחר את הכותרת הטובה ביותר (הארוכה ביותר)
            best = max(group, key=lambda a: len(a['title']))

            scored.append({
                'title': best['title'],
                'summary': best['summary'],
                'url': best['url'],
                'category': best['category'],
                'sources': sources,
                'num_sources': num_sources,
                'score': score,
                'is_exclusive': has_exclusive,
                'importance': best.get('importance', 'medium'),
                'published_at': best['published_at'],
                'all_urls': [a['url'] for a in group],
                'keywords': best.get('keywords', []),
            })

        # מיין לפי ניקוד
        scored.sort(key=lambda x: x['score'], reverse=True)

        print(f"  {len(articles)} ידיעות → {len(scored)} נושאים ייחודיים")
        multi = sum(1 for s in scored if s['num_sources'] >= 2)
        print(f"  מתוכם {multi} נושאים עם 2+ מקורות")

        return scored

    def _group_by_similarity(self, articles: List[Dict]) -> Dict[str, List[Dict]]:
        """קיבוץ ידיעות דומות"""
        groups = {}

        for article in articles:
            dk = (article.get('duplicate_key') or '').strip()
            title_words = set(self._clean_text(article['title']).split())

            # חפש group קיים שדומה
            matched_key = None
            for existing_key, group in groups.items():
                # בדוק דמיון duplicate_key
                if dk and existing_key == dk:
                    matched_key = existing_key
                    break

                # בדוק דמיון Jaccard על כותרות
                existing_words = set(self._clean_text(group[0]['title']).split())
                if self._jaccard(title_words, existing_words) >= config.SIMILARITY_THRESHOLD:
                    matched_key = existing_key
                    break

            if matched_key:
                groups[matched_key].append(article)
            else:
                key = dk if dk else article['title'][:50]
                groups[key] = [article]

        return groups

    def _clean_text(self, text: str) -> str:
        """ניקוי טקסט לצורך השוואה"""
        text = re.sub(r'[^\w\s]', ' ', text)
        stop_words = {'את', 'של', 'על', 'אל', 'עם', 'בין', 'לפי', 'אחרי',
                      'לפני', 'כי', 'או', 'גם', 'רק', 'הוא', 'היא', 'זה',
                      'אם', 'לא', 'כל', 'יותר', 'עוד', 'כבר', 'מאד'}
        words = [w for w in text.split() if w not in stop_words and len(w) > 2]
        return ' '.join(words[:12])

    def _jaccard(self, set1: set, set2: set) -> float:
        """Jaccard similarity"""
        if not set1 or not set2:
            return 0.0
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        return intersection / union if union > 0 else 0.0


# ============================================================
# Class: BulletinGenerator — הפקת מבזקים
# ============================================================

class BulletinGenerator:
    """מפיק מבזק חדשותי — עם Claude או בפורמט קבוע"""

    def generate(
        self,
        topics: List[Dict],
        categories: Optional[List[str]] = None,
        hours: int = 24,
        style: str = 'flash',
        max_items: int = 30,
    ) -> str:
        """הפקת מבזק"""
        print("\n" + "=" * 60)
        print("📝 שלב 4: הפקת מבזק")
        print("=" * 60)

        # סינון לפי קטגוריות
        if categories:
            topics = [t for t in topics if t['category'] in categories]

        # סינון לפי זמן
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        filtered = []
        for t in topics:
            try:
                pub = datetime.fromisoformat(t['published_at'])
                if pub.tzinfo is None:
                    pub = pub.replace(tzinfo=timezone.utc)
                if pub >= cutoff:
                    filtered.append(t)
            except Exception:
                filtered.append(t)  # אם לא ניתן לפרסר, כלול

        topics = filtered[:max_items]

        print(f"  {len(topics)} ידיעות אחרי סינון")
        print(f"  סגנון: {style}, טווח: {hours} שעות")
        if categories:
            print(f"  קטגוריות: {', '.join(categories)}")

        # נסה Claude, אם לא — fallback
        client = get_anthropic()
        if client and len(topics) > 0:
            return self._generate_with_claude(topics, categories, hours, style, max_items, client)
        else:
            return self._generate_basic(topics, categories, hours, style)

    def _generate_with_claude(
        self, topics, categories, hours, style, max_items, client
    ) -> str:
        """הפקת מבזק עם Claude"""
        # הכן את הידיעות כטקסט
        items_text = ""
        for i, t in enumerate(topics, 1):
            items_text += f"\n{i}. [{t['category']}] {t['title']}"
            if t['summary']:
                items_text += f"\n   {t['summary'][:200]}"
            items_text += f"\n   מקורות: {', '.join(t['sources'])} ({t['num_sources']} מקורות)"
            if t['is_exclusive']:
                items_text += " [בלעדי]"
            items_text += "\n"

        cat_str = ', '.join(categories) if categories else 'הכל'
        prompt = config.BULLETIN_PROMPT.format(
            style=style,
            max_items=max_items,
            categories=cat_str,
            hours=hours,
            news_items=items_text,
        )

        try:
            response = client.messages.create(
                model=config.BULLETIN_MODEL,
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}]
            )
            bulletin = response.content[0].text.strip()
            print("  ✅ מבזק נוצר עם Claude")
            return bulletin
        except Exception as e:
            print(f"  ⚠️  שגיאת Claude: {e}, עובר ל-fallback")
            return self._generate_basic(topics, categories, hours, style)

    def _generate_basic(self, topics, categories, hours, style) -> str:
        """הפקת מבזק ללא AI"""
        now = datetime.now()
        cat_str = ', '.join(categories) if categories else 'כללי'

        lines = []
        lines.append(f"# 📋 מבזק חדשות — {cat_str}")
        lines.append(f"**⏰ {hours} שעות אחרונות | {len(topics)} ידיעות | {now.strftime('%d/%m/%Y %H:%M')}**")
        lines.append("")
        lines.append("---")
        lines.append("")

        # קבץ לפי קטגוריה
        by_cat = defaultdict(list)
        for t in topics:
            by_cat[t['category']].append(t)

        cat_labels = {
            'security': '🔴 ביטחון', 'politics': '🏛️ פוליטיקה',
            'diplomatic': '🌍 מדיני', 'economy': '💰 כלכלה',
            'stocks': '📊 בורסה', 'haredi': '📿 חרדי',
            'arab': '🌙 ערבי', 'health': '🏥 בריאות',
            'culture': '🎭 תרבות', 'local': '📍 מקומי',
            'legal': '⚖️ משפטי', 'sports': '⚽ ספורט',
            'tech': '💻 טכנולוגיה', 'general': '📰 כללי',
        }

        # סדר קטגוריות קבוע
        cat_order = ['security', 'politics', 'diplomatic', 'economy', 'stocks',
                     'haredi', 'arab', 'health', 'legal', 'local',
                     'culture', 'sports', 'tech', 'general']

        for cat in cat_order:
            if cat not in by_cat:
                continue
            cat_topics = by_cat[cat]
            label = cat_labels.get(cat, f'📌 {cat}')
            lines.append(f"## {label}")
            lines.append("")

            for t in cat_topics:
                # נקה את הכותרת משם האתר בסוף (דפוס נפוץ: "כותרת - שם אתר")
                title = self._clean_title(t['title'], t['sources'])
                exclusive_mark = " 🔥" if t['is_exclusive'] else ""

                # פרסר זמן פרסום
                pub_time = ""
                try:
                    pub = datetime.fromisoformat(t['published_at'])
                    pub_time = pub.strftime('%H:%M')
                except Exception:
                    pass

                # קישור לידיעה
                link = t.get('url', '')

                # מקורות
                sources_str = ', '.join(t['sources'])
                num = t['num_sources']
                sources_display = f"({sources_str})" if num <= 3 else f"({num} מקורות)"

                if style == 'flash':
                    time_prefix = f"**{pub_time}** | " if pub_time else ""
                    if link:
                        lines.append(f"• {time_prefix}[{title}]({link}){exclusive_mark} {sources_display}")
                    else:
                        lines.append(f"• {time_prefix}{title}{exclusive_mark} {sources_display}")

                elif style == 'brief':
                    time_prefix = f"🕐 {pub_time} | " if pub_time else ""
                    if link:
                        lines.append(f"**[{title}]({link})**{exclusive_mark}")
                    else:
                        lines.append(f"**{title}**{exclusive_mark}")
                    if t['summary']:
                        lines.append(f"{t['summary'][:200]}")
                    lines.append(f"_{time_prefix}{sources_display}_")
                    lines.append("")

                else:  # detailed
                    time_prefix = f"🕐 {pub_time} | " if pub_time else ""
                    if link:
                        lines.append(f"### [{title}]({link}){exclusive_mark}")
                    else:
                        lines.append(f"### {title}{exclusive_mark}")
                    if t['summary']:
                        lines.append(f"{t['summary'][:400]}")
                    lines.append(f"_{time_prefix}מקורות ({num}): {sources_str}_")
                    lines.append("")

            lines.append("")

        lines.append("---")
        all_sources = set()
        for t in topics:
            all_sources.update(t['sources'])
        lines.append(f"**סה\"כ {len(topics)} ידיעות מ-{len(all_sources)} מקורות**")

        return '\n'.join(lines)

    def _clean_title(self, title: str, sources: List[str]) -> str:
        """ניקוי כותרת — הסרת שם האתר מהסוף"""
        # הסר דפוסים כמו " - Ynet" או " | גלובס" מסוף הכותרת
        for source in sources:
            for sep in [' - ', ' | ', ' – ', ' — ']:
                # בדיקה case-insensitive
                for variant in [source, source.lower(), source.upper()]:
                    suffix = f"{sep}{variant}"
                    if title.lower().endswith(suffix.lower()):
                        title = title[:-len(suffix)]
                        break
        # הסר גם דפוסים כלליים של " - domain.co.il" או " - שם אתר"
        title = re.sub(r'\s*[-|–—]\s*\S+\.\S+\.\S+\s*$', '', title)
        # הסר " - ynet" ודומיו שנשארו
        title = re.sub(r'\s*[-|–—]\s*(ynet|Ynet|Mako|mako|i24NEWS|Calcalist|N12)\s*$', '', title, flags=re.IGNORECASE)
        return title.strip()


# ============================================================
# Class: DatabaseManager — שמירה ב-Supabase
# ============================================================

class DatabaseManager:
    """שמירה ושליפה מ-Supabase"""

    def save_articles(self, articles: List[Dict]) -> int:
        """שמירת ידיעות ב-Supabase (batch upsert)"""
        client = get_supabase()
        if not client:
            print("  ⚠️  Supabase לא מחובר — דילוג על שמירה")
            return 0

        rows = []
        for article in articles:
            rows.append({
                'title': article['title'],
                'summary': article.get('summary', ''),
                'url': article['url'],
                'url_hash': article['url_hash'],
                'source_name': article['source_name'],
                'source_sector': article.get('source_sector', ''),
                'language': article.get('language', 'he'),
                'category': article.get('category'),
                'keywords': article.get('keywords', []),
                'importance': article.get('importance', 'medium'),
                'duplicate_key': article.get('duplicate_key', ''),
                'is_exclusive': article.get('is_exclusive', False),
                'score': article.get('score', 10),
                'published_at': article.get('published_at'),
                'classified': article.get('classified', False),
            })

        saved = 0
        batch_size = 50
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            try:
                client.table('news_items').upsert(
                    batch, on_conflict='url_hash'
                ).execute()
                saved += len(batch)
            except Exception as e:
                print(f"  ⚠️  שגיאת שמירה באצ' {i // batch_size + 1}: {e}")

        print(f"  💾 נשמרו {saved}/{len(articles)} ידיעות ב-Supabase")
        return saved

    def load_articles(
        self,
        hours: int = 24,
        categories: Optional[List[str]] = None,
    ) -> List[Dict]:
        """שליפת ידיעות מ-Supabase"""
        client = get_supabase()
        if not client:
            return []

        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        query = client.table('news_items').select('*').gte('collected_at', cutoff)

        if categories:
            query = query.in_('category', categories)

        query = query.order('score', desc=True).limit(500)

        try:
            result = query.execute()
            articles = [self._normalize_db_row(row) for row in result.data]
            print(f"  📂 נטענו {len(articles)} ידיעות מ-Supabase")
            return articles
        except Exception as e:
            print(f"  ⚠️  שגיאת שליפה: {e}")
            return []

    def _normalize_db_row(self, row: Dict) -> Dict:
        """המרת שורת DB למבנה אחיד שמתאים ל-TopicMerger"""
        row['is_exclusive'] = bool(row.get('is_exclusive', False))
        row['score'] = int(row.get('score', 10))
        row['keywords'] = row.get('keywords') or []
        row['source_sector'] = row.get('source_sector', '')
        row['classified'] = bool(row.get('classified', False))
        row['importance'] = row.get('importance', 'medium')
        row['duplicate_key'] = row.get('duplicate_key') or ''
        row['summary'] = row.get('summary') or ''
        row['title'] = row.get('title') or ''
        row['source_name'] = row.get('source_name') or 'unknown'
        row['url'] = row.get('url') or ''
        row['published_at'] = row.get('published_at') or datetime.now(timezone.utc).isoformat()
        return row

    def cleanup_old(self, days: int = 30) -> int:
        """מחיקת ידיעות ישנות מה-DB"""
        client = get_supabase()
        if not client:
            return 0
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        try:
            result = client.table('news_items').delete().lt('collected_at', cutoff).execute()
            deleted = len(result.data) if result.data else 0
            print(f"  🗑️  נמחקו {deleted} ידיעות ישנות מ-{days} ימים")
            return deleted
        except Exception as e:
            print(f"  ⚠️  שגיאת מחיקה: {e}")
            return 0

    def log_run(self, items_collected, items_classified, sources_ok, sources_fail, errors):
        """לוג של ריצה"""
        client = get_supabase()
        if not client:
            return
        try:
            client.table('collection_runs').insert({
                'items_collected': items_collected,
                'items_classified': items_classified,
                'sources_succeeded': sources_ok,
                'sources_failed': sources_fail,
                'errors': errors[:10],  # מקסימום 10 שגיאות
                'finished_at': datetime.now(timezone.utc).isoformat(),
            }).execute()
        except Exception:
            pass


# ============================================================
# Main Pipeline
# ============================================================

class NewsPipeline:
    """הצנרת המלאה: איסוף → סיווג → איחוד → שמירה → מבזק"""

    def __init__(self):
        self.collector = NewsCollector()
        self.classifier = NewsClassifier()
        self.merger = TopicMerger()
        self.bulletin_gen = BulletinGenerator()
        self.db = DatabaseManager()

    def run_collection(self) -> List[Dict]:
        """שלב 1-3: איסוף, סיווג, איחוד"""
        # איסוף
        articles = self.collector.collect_all()

        if not articles:
            print("❌ לא נאספו ידיעות!")
            return []

        # סיווג
        articles = self.classifier.classify_all(articles)

        # שמירה ב-DB
        self.db.save_articles(articles)

        # איחוד
        topics = self.merger.merge_and_rank(articles)

        # לוג
        self.db.log_run(
            items_collected=len(articles),
            items_classified=sum(1 for a in articles if a.get('classified')),
            sources_ok=self.collector.sources_ok,
            sources_fail=self.collector.sources_fail,
            errors=self.collector.errors,
        )

        # ניקוי ידיעות ישנות (פעם בריצה)
        self.db.cleanup_old(days=30)

        return topics

    def generate_bulletin(
        self,
        topics: Optional[List[Dict]] = None,
        categories: Optional[List[str]] = None,
        hours: int = 24,
        style: str = 'flash',
        max_items: int = 30,
        from_db: bool = False,
    ) -> str:
        """שלב 4: הפקת מבזק"""
        if from_db and not topics:
            # שלוף מ-DB
            articles = self.db.load_articles(hours=hours, categories=categories)
            if articles:
                # המר לפורמט topics
                topics = self.merger.merge_and_rank(articles)

        if not topics:
            return "❌ אין ידיעות להצגה"

        return self.bulletin_gen.generate(
            topics=topics,
            categories=categories,
            hours=hours,
            style=style,
            max_items=max_items,
        )

    def run_full(
        self,
        categories: Optional[List[str]] = None,
        hours: int = 24,
        style: str = 'flash',
        max_items: int = 30,
    ) -> str:
        """הצנרת המלאה: איסוף → סיווג → איחוד → מבזק"""
        print("\n" + "🚀" * 20)
        print("  מחולל מבזקי חדשות ישראל — v2.0")
        print("🚀" * 20 + "\n")

        topics = self.run_collection()
        if not topics:
            return "❌ לא נאספו ידיעות"

        bulletin = self.generate_bulletin(
            topics=topics,
            categories=categories,
            hours=hours,
            style=style,
            max_items=max_items,
        )

        return bulletin


# ============================================================
# CLI
# ============================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description='מחולל מבזקי חדשות ישראל v2.0')
    parser.add_argument('--style', choices=['flash', 'brief', 'detailed'], default='flash',
                        help='סגנון המבזק')
    parser.add_argument('--hours', type=int, default=24,
                        help='טווח זמן בשעות')
    parser.add_argument('--max', type=int, default=30,
                        help='מקסימום ידיעות')
    parser.add_argument('--categories', nargs='+', default=None,
                        help='קטגוריות (security economy haredi arab ...)')
    parser.add_argument('--collect-only', action='store_true',
                        help='רק איסוף וסיווג, ללא הפקת מבזק')
    parser.add_argument('--from-db', action='store_true',
                        help='שלוף מ-Supabase במקום לאסוף מחדש')
    parser.add_argument('--output', type=str, default=None,
                        help='שמור לקובץ')
    args = parser.parse_args()

    pipeline = NewsPipeline()

    if args.collect_only:
        topics = pipeline.run_collection()
        print(f"\n✅ נאספו ומסווגו {len(topics)} נושאים")
        return

    if args.from_db:
        bulletin = pipeline.generate_bulletin(
            categories=args.categories,
            hours=args.hours,
            style=args.style,
            max_items=args.max,
            from_db=True,
        )
    else:
        bulletin = pipeline.run_full(
            categories=args.categories,
            hours=args.hours,
            style=args.style,
            max_items=args.max,
        )

    # שמירה
    if args.output:
        filename = args.output
    else:
        filename = f"bulletin_{datetime.now().strftime('%Y%m%d_%H%M')}.md"

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(bulletin)
    print(f"\n📄 המבזק נשמר: {filename}")

    # הדפסה
    print("\n" + "=" * 60)
    print(bulletin)
    print("=" * 60)


if __name__ == '__main__':
    main()
