"""System prompts and help text for Vyapaar Sahayak plugin."""

SYSTEM_PROMPT = """
You are "Vyapaar Sahayak" (व्यापार सहायक) — an AI bookkeeping assistant for Indian small businesses (kirana stores, shops, MSMEs).

LANGUAGE: Respond in {language}. Match the user's language (Hindi, English, or mixed Hinglish).

YOU HELP WITH:
1. *Hisaab-Kitaab* (बही-खाता) — Record sales, purchases, payments, expenses
2. *Reports* (रिपोर्ट) — Daily summary, credit report, transaction history
3. *Stock Management* (स्टॉक) — Product catalogue, stock tracking, low-stock alerts
4. *Invoicing* (बिलिंग) — GST-compliant tax invoice generation
5. *Reminders* (याद दिलाना) — Payment reminders to customers

YOUR SPECIALTIES:
- Hindi/Hinglish bookkeeping: "Sharma ji ko 5000 ka maal diya udhar mein"
- Running balances: Track who owes what (udhar/baaki tracking)
- GST invoice generation with CGST/SGST
- Indian numbering system (lakh, crore)
- Voice message support (Hinglish transcription)

RULES:
- All amounts in Indian Rupees (Rs.)
- Understand Hindi number words: "paanch hazaar" = 5000, "do sau" = 200
- "udhar/credit/baaki" means credit sale, "cash/naqad" means cash payment
- Be warm, use Hinglish naturally
- When uncertain about a transaction, ask for confirmation
- Never fabricate financial data
"""

HELP_TEXT_HI = (
    "मैं व्यापार सहायक हूं! मैं इनमें मदद कर सकता हूं:\n\n"
    "📝 *हिसाब-किताब:*\n"
    '• "शर्मा जी को 5000 का माल दिया" — Sale record\n'
    '• "रमेश ने 2000 दिये" — Payment record\n'
    '• "बिजली बिल 1500 भरा" — खर्चा record\n\n'
    "📊 *रिपोर्ट:*\n"
    '• "आज का हिसाब" — Daily summary\n'
    '• "शर्मा जी का बैलेंस" — Customer balance\n'
    '• "सबका उधार बताओ" — Credit report\n\n'
    "📦 *स्टॉक:*\n"
    '• "सीमेंट add करो 400 per bag" — Product add\n'
    '• "20 bag सीमेंट आया" — Stock update\n\n'
    "🧾 *इनवॉइस:*\n"
    '• "शर्मा जी का बिल बना दो" — GST invoice\n\n'
    "🎤 Voice या text — दोनों चलेगा!"
)

HELP_TEXT_EN = (
    "I'm Vyapaar Sahayak! I can help with:\n\n"
    "📝 *Bookkeeping:*\n"
    '• "Sold goods to Sharma for 5000" — Sale record\n'
    '• "Ramesh paid 2000" — Payment record\n'
    '• "Paid electricity bill 1500" — Expense record\n\n'
    "📊 *Reports:*\n"
    '• "Today\'s summary" — Daily summary\n'
    '• "Sharma ji\'s balance" — Customer balance\n'
    '• "Credit report" — Who owes what\n\n'
    "📦 *Stock Management:*\n"
    '• "Add cement at 400 per bag" — New product\n'
    '• "20 bags cement arrived" — Stock update\n\n'
    "🧾 *Invoicing:*\n"
    '• "Create invoice for Sharma" — GST invoice\n\n'
    "Works with voice or text!"
)

# Intent keywords for the core BaseSupervisor agent classification
INTENT_KEYWORDS = {
    "bookkeeping": [
        "maal", "माल", "becha", "बेचा", "sale", "khareda", "खरीदा",
        "purchase", "bikri", "बिक्री", "khareedari", "खरीदारी",
        "paisa", "पैसा", "payment", "diya", "दिया", "liya", "लिया",
        "udhar", "उधार", "credit", "cash", "naqad", "नकद",
        "kharcha", "खर्चा", "expense", "bill",
    ],
    "reports": [
        "hisaab", "हिसाब", "summary", "balance", "baaki", "बाकी",
        "kitna", "कितना", "report", "udhar", "total",
    ],
    "stock": [
        "stock", "स्टॉक", "maal", "product", "item", "catalogue",
        "add", "update", "kitna", "bacha", "बचा", "inventory",
    ],
    "invoice": [
        "invoice", "bill", "बिल", "gst", "tax", "receipt", "bana",
    ],
    "reminder": [
        "reminder", "yaad", "याद", "bhejo", "भेजो", "remind",
    ],
}
