"""
SEC EDGAR 13F Parser
====================

Fetches and parses institutional holdings from SEC EDGAR 13F filings.
Free data source with quarterly frequency and 45-day delay.

medallion: silver
"""

import logging
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional
import requests

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# SEC EDGAR API base URL
EDGAR_BASE_URL = "https://www.sec.gov"
EDGAR_FULL_TEXT_URL = f"{EDGAR_BASE_URL}/cgi-bin/browse-edgar"

# User-Agent required by SEC for programmatic access
SEC_USER_AGENT = "AxiomFolio/1.0 (contact@axiomfolio.com)"


def parse_13f_xml(xml_content: str) -> List[Dict]:
    """Parse 13F-HR XML filing and extract holdings.

    Returns list of holdings with: symbol, shares, value, filing info.
    """
    holdings = []
    try:
        root = ET.fromstring(xml_content)

        # 13F filings use namespace - handle both with and without
        ns = {
            "": "http://www.sec.gov/edgar/document/thirteenf/informationtable"
        }

        # Find all infoTable entries
        info_tables = root.findall(".//infoTable", ns) or root.findall(".//infoTable")

        for entry in info_tables:
            try:
                # Extract fields
                name_of_issuer = _get_text(entry, "nameOfIssuer", ns)
                cusip = _get_text(entry, "cusip", ns)
                value = _get_int(entry, "value", ns)  # In thousands
                shares = _get_int(entry, "sshPrnamt", ns)
                share_class = _get_text(entry, "titleOfClass", ns)

                # Map CUSIP to ticker symbol (basic mapping)
                symbol = _cusip_to_symbol(cusip, name_of_issuer)

                if symbol:
                    holdings.append({
                        "symbol": symbol,
                        "name_of_issuer": name_of_issuer,
                        "cusip": cusip,
                        "shares": shares,
                        "value_thousands": value,
                        "share_class": share_class,
                    })
            except Exception as e:
                logger.debug("Failed to parse 13F entry: %s", e)

    except ET.ParseError as e:
        logger.warning("Failed to parse 13F XML: %s", e)

    return holdings


def _get_text(element, tag: str, ns: Dict) -> Optional[str]:
    """Get text content of a child element."""
    child = element.find(tag, ns) or element.find(tag)
    return child.text.strip() if child is not None and child.text else None


def _get_int(element, tag: str, ns: Dict) -> Optional[int]:
    """Get integer value from a child element."""
    text = _get_text(element, tag, ns)
    if text:
        try:
            return int(text.replace(",", ""))
        except ValueError:
            pass
    return None


def _cusip_to_symbol(cusip: str, issuer_name: str) -> Optional[str]:
    """Map CUSIP to ticker symbol.

    This is a simplified mapping. In production, would use a CUSIP database
    or OpenFIGI API for accurate mapping.
    """
    # Known major CUSIP mappings (top holdings)
    CUSIP_MAP = {
        "037833100": "AAPL",
        "594918104": "MSFT",
        "02079K305": "GOOGL",
        "02079K107": "GOOG",
        "023135106": "AMZN",
        "88160R101": "TSLA",
        "30303M102": "META",
        "67066G104": "NVDA",
        "084670702": "BRK-B",
        "11135F101": "BRK-A",
        "92826C839": "V",
        "22160K105": "COST",
        "46625H100": "JPM",
        "478160104": "JNJ",
        "931142103": "WMT",
        "742718109": "PG",
        "87612E106": "TGT",
        "172967424": "C",
        "084670108": "BRK-A",
    }

    if cusip and cusip in CUSIP_MAP:
        return CUSIP_MAP[cusip]

    # Fallback: try to extract from issuer name (very rough)
    # In production, use a proper CUSIP lookup service
    return None


def fetch_recent_13f_filings(
    days_back: int = 90,
    max_filings: int = 100,
) -> List[Dict]:
    """Fetch recent 13F-HR filings from SEC EDGAR.

    Returns list of filing metadata (not full holdings).
    """
    filings = []

    try:
        # Use EDGAR full-text search for 13F-HR filings
        params = {
            "action": "getcurrent",
            "type": "13F-HR",
            "count": max_filings,
            "output": "atom",
        }
        headers = {"User-Agent": SEC_USER_AGENT}

        response = requests.get(
            EDGAR_FULL_TEXT_URL,
            params=params,
            headers=headers,
            timeout=30,
        )

        if response.status_code != 200:
            logger.warning("EDGAR API returned status %d", response.status_code)
            return filings

        # Parse atom feed
        root = ET.fromstring(response.content)
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        entries = root.findall(".//atom:entry", ns)
        for entry in entries:
            try:
                title = entry.find("atom:title", ns)
                link = entry.find("atom:link", ns)
                updated = entry.find("atom:updated", ns)

                if title is not None and link is not None:
                    filings.append({
                        "title": title.text,
                        "url": link.get("href"),
                        "updated": updated.text if updated is not None else None,
                    })
            except Exception as e:
                logger.debug("Failed to parse filing entry: %s", e)

    except Exception as e:
        logger.warning("Failed to fetch 13F filings: %s", e)

    return filings


def fetch_and_parse_13f(filing_url: str) -> Dict:
    """Fetch a specific 13F filing and parse its holdings.

    Args:
        filing_url: URL to the filing index page

    Returns:
        Dict with institution info and holdings list
    """
    result = {
        "institution_cik": None,
        "institution_name": None,
        "filing_date": None,
        "period_date": None,
        "holdings": [],
    }

    headers = {"User-Agent": SEC_USER_AGENT}

    try:
        # First, get the filing index to find the XML file
        response = requests.get(filing_url, headers=headers, timeout=30)
        if response.status_code != 200:
            return result

        # Find the primary document (infotable.xml or similar)
        # This is simplified - real implementation would parse index
        xml_url = None
        content = response.text

        # Look for links to XML files
        import re
        xml_matches = re.findall(r'href="([^"]+\.xml)"', content, re.IGNORECASE)
        for match in xml_matches:
            if "infotable" in match.lower() or "13f" in match.lower():
                xml_url = f"{EDGAR_BASE_URL}{match}" if match.startswith("/") else match
                break

        if not xml_url:
            logger.warning("No XML file found in filing")
            return result

        # Fetch and parse the XML
        xml_response = requests.get(xml_url, headers=headers, timeout=30)
        if xml_response.status_code == 200:
            result["holdings"] = parse_13f_xml(xml_response.text)

    except Exception as e:
        logger.warning("Failed to fetch/parse 13F from %s: %s", filing_url, e)

    return result


def persist_13f_holdings(
    db: Session,
    institution_cik: str,
    institution_name: str,
    filing_date: date,
    period_date: date,
    holdings: List[Dict],
) -> int:
    """Persist 13F holdings to database.

    Returns count of holdings inserted.
    """
    from app.models.institutional_holding import InstitutionalHolding

    inserted = 0

    for h in holdings:
        symbol = h.get("symbol")
        if not symbol:
            continue

        try:
            # Check if we already have this filing/symbol combo
            existing = db.query(InstitutionalHolding).filter(
                InstitutionalHolding.symbol == symbol,
                InstitutionalHolding.filing_date == filing_date,
                InstitutionalHolding.institution_cik == institution_cik,
            ).first()

            if existing:
                # Update existing
                existing.shares = h.get("shares")
                existing.value_usd = (h.get("value_thousands") or 0) * 1000
                existing.share_class = h.get("share_class")
            else:
                # Insert new
                db.add(InstitutionalHolding(
                    symbol=symbol,
                    filing_date=filing_date,
                    period_date=period_date,
                    institution_cik=institution_cik,
                    institution_name=institution_name,
                    shares=h.get("shares"),
                    value_usd=(h.get("value_thousands") or 0) * 1000,
                    share_class=h.get("share_class"),
                ))
                inserted += 1

        except Exception as e:
            logger.debug("Failed to persist holding %s: %s", symbol, e)

    return inserted
