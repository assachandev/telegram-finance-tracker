import calendar
import logging
from datetime import datetime

from telegram import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from src import formatter, storage
from src.config import TIMEZONE, is_authorized

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Reply keyboards
# ---------------------------------------------------------------------------

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [["➕ Add Transaction"], ["📊 Summary", "📋 Reports"], ["🕐 Recent", "⚙️ Settings"]],
    resize_keyboard=True,
)

REPORTS_KEYBOARD = ReplyKeyboardMarkup(
    [["📅 Today", "📆 This Month"], ["🗓 This Year"], ["🏠 Main Menu"]],
    resize_keyboard=True,
)

SETTINGS_KEYBOARD = ReplyKeyboardMarkup(
    [["📂 Categories", "🗑 Delete Last"], ["🏠 Main Menu"]],
    resize_keyboard=True,
)

# ---------------------------------------------------------------------------
# Conversation states — Add Transaction
# ---------------------------------------------------------------------------
SELECT_TYPE, SELECT_CATEGORY, SELECT_METHOD, ENTER_AMOUNT, ENTER_NOTE, CONFIRM = range(6)

# Conversation states — Category Management
CAT_TYPE, CAT_ACTION, CAT_ADD_NAME, CAT_REMOVE_SELECT = range(10, 14)

# Callback data
CB_TYPE = "type"
CB_CAT = "cat"
CB_METHOD = "method"
CB_CONFIRM = "confirm"
CB_CANCEL = "cancel"
CB_SKIP = "skip"
CB_CAT_TYPE = "cattype"
CB_CAT_ACTION = "cataction"
CB_CAT_REMOVE = "catremove"
CB_DEL_CONFIRM = "dlconf"
CB_DEL_CANCEL = "dlcancel"

TYPE_LABELS = {"expense": "💸 Expense", "income": "💰 Income"}
METHOD_LABELS = {"cash": "💵 Cash", "transfer": "🏦 Transfer"}


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------

async def _check_auth(update: Update) -> bool:
    if not is_authorized(update.effective_chat.id):
        await update.effective_message.reply_text("⛔ Unauthorized.")
        return False
    return True


# ---------------------------------------------------------------------------
# Auto-cancel helper
# Wraps a non-conversation handler so it can be used as a conversation fallback.
# Clears user_data, runs the target handler, ends the conversation.
# ---------------------------------------------------------------------------

def _interrupt(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        context.user_data.clear()
        await func(update, context)
        return ConversationHandler.END
    return wrapper


# ---------------------------------------------------------------------------
# /start
# ---------------------------------------------------------------------------

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _check_auth(update):
        return
    await update.message.reply_text(
        "👋 <b>Finance Tracker</b>\n\nUse the menu below to get started.",
        parse_mode=ParseMode.HTML,
        reply_markup=MAIN_KEYBOARD,
    )


# ---------------------------------------------------------------------------
# Add Transaction — conversation flow
# ---------------------------------------------------------------------------

async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await _check_auth(update):
        return ConversationHandler.END

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data=f"{CB_TYPE}:{key}")]
        for key, label in TYPE_LABELS.items()
    ])
    await update.message.reply_text("Select transaction type:", reply_markup=keyboard)
    return SELECT_TYPE


async def select_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query: CallbackQuery = update.callback_query
    await query.answer()

    tx_type = query.data.split(":")[1]
    context.user_data["tx_type"] = tx_type

    cats = storage.get_categories().get(tx_type, [])
    rows = [
        [InlineKeyboardButton(c, callback_data=f"{CB_CAT}:{c}") for c in cats[i:i + 3]]
        for i in range(0, len(cats), 3)
    ]
    await query.edit_message_text(
        f"{TYPE_LABELS[tx_type]} — Select category:",
        reply_markup=InlineKeyboardMarkup(rows),
    )
    return SELECT_CATEGORY


async def select_category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query: CallbackQuery = update.callback_query
    await query.answer()

    category = query.data.split(":", 1)[1]
    context.user_data["category"] = category

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data=f"{CB_METHOD}:{key}")]
        for key, label in METHOD_LABELS.items()
    ])
    await query.edit_message_text(
        f"Category: <b>{category}</b>\n\nPaid with:",
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard,
    )
    return SELECT_METHOD


async def select_method_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query: CallbackQuery = update.callback_query
    await query.answer()

    method = query.data.split(":")[1]
    context.user_data["method"] = method

    await query.edit_message_text(
        f"Method: <b>{METHOD_LABELS[method]}</b>\n\nEnter amount:",
        parse_mode=ParseMode.HTML,
    )
    return ENTER_AMOUNT


async def enter_amount_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip().replace(",", "")
    try:
        amount = float(text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Invalid amount. Enter a positive number:")
        return ENTER_AMOUNT

    context.user_data["amount"] = amount
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⏭ Skip", callback_data=CB_SKIP)]])
    await update.message.reply_text(
        "Add a note? (optional)",
        reply_markup=keyboard,
    )
    return ENTER_NOTE


async def enter_note_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["note"] = update.message.text.strip()[:200]
    return await _show_confirm(update, context, edit=False)


async def skip_note_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query: CallbackQuery = update.callback_query
    await query.answer()
    context.user_data["note"] = ""
    return await _show_confirm(update, context, edit=True, query=query)


async def _show_confirm(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    edit: bool = False,
    query: CallbackQuery | None = None,
) -> int:
    tx_type = context.user_data["tx_type"]
    category = context.user_data["category"]
    method = context.user_data["method"]
    amount = context.user_data["amount"]
    note = context.user_data.get("note", "")

    note_line = f"\n📝 <i>{note}</i>" if note else ""
    text = (
        f"<b>Confirm Transaction</b>\n\n"
        f"{TYPE_LABELS[tx_type]}  ·  {METHOD_LABELS[method]}\n"
        f"📂 {category}\n"
        f"💵 {amount:,.0f}"
        f"{note_line}\n\n"
        f"Save this transaction?"
    )
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Confirm", callback_data=CB_CONFIRM),
        InlineKeyboardButton("❌ Cancel", callback_data=CB_CANCEL),
    ]])

    if edit and query:
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
    return CONFIRM


async def confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query: CallbackQuery = update.callback_query
    await query.answer()

    if query.data == CB_CANCEL:
        context.user_data.clear()
        await query.edit_message_text("❌ Cancelled.")
        return ConversationHandler.END

    tx_type = context.user_data["tx_type"]
    category = context.user_data["category"]
    method = context.user_data["method"]
    amount = context.user_data["amount"]
    note = context.user_data.get("note", "")

    try:
        storage.append_transaction(tx_type, category, amount, method, note)
        month_rows = storage.get_this_month()
        text = formatter.format_after_save(tx_type, category, amount, method, month_rows)
        await query.edit_message_text(text, parse_mode=ParseMode.HTML)
    except Exception as exc:
        logger.error("Failed to save transaction: %s", exc)
        await query.edit_message_text("❌ Error saving transaction. Please try again.")

    context.user_data.clear()
    return ConversationHandler.END


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("❌ Cancelled.", reply_markup=MAIN_KEYBOARD)
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

async def summary_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _check_auth(update):
        return
    all_rows = storage.get_all()
    if not all_rows:
        await update.message.reply_text("No transactions recorded yet.")
        return
    month_rows = storage.get_this_month()
    text = formatter.format_summary(all_rows, month_rows)
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

async def reports_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _check_auth(update):
        return
    await update.message.reply_text("Select a report:", reply_markup=REPORTS_KEYBOARD)


async def report_today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _check_auth(update):
        return
    today_rows = storage.get_today()
    if not today_rows:
        await update.message.reply_text("No transactions recorded today.")
        return
    month_rows = storage.get_this_month()
    text = formatter.format_daily_report(today_rows, month_rows)
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def report_monthly(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _check_auth(update):
        return
    this_rows = storage.get_this_month()
    if not this_rows:
        await update.message.reply_text("No transactions this month.")
        return
    last_rows = storage.get_last_month()
    text = formatter.format_monthly_report(this_rows, last_rows)
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def report_yearly(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _check_auth(update):
        return
    year_rows = storage.get_this_year()
    if not year_rows:
        await update.message.reply_text("No transactions this year.")
        return
    text = formatter.format_yearly_report(year_rows)
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _check_auth(update):
        return
    await update.message.reply_text("Main menu.", reply_markup=MAIN_KEYBOARD)


async def recent_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _check_auth(update):
        return
    rows = storage.get_recent(10)
    text = formatter.format_recent(rows)
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _check_auth(update):
        return
    await update.message.reply_text("⚙️ <b>Settings</b>", parse_mode=ParseMode.HTML, reply_markup=SETTINGS_KEYBOARD)


# ---------------------------------------------------------------------------
# Delete Last Transaction
# ---------------------------------------------------------------------------

async def delete_last_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _check_auth(update):
        return

    all_rows = storage.get_all()
    if not all_rows:
        await update.message.reply_text("No transactions to delete.")
        return

    last = all_rows[-1]
    method_label = formatter.METHOD_LABELS.get(last.get("method", ""), last.get("method", ""))
    type_label = formatter.TYPE_LABELS.get(last.get("type", ""), last.get("type", ""))

    text = (
        f"🗑 <b>Delete Last Transaction?</b>\n\n"
        f"{type_label}  ·  {method_label}\n"
        f"📂 {last['category']}\n"
        f"💵 {last['amount']:,.0f}\n"
        f"📅 {last['date']}"
    )
    if last.get("note"):
        text += f"\n📝 <i>{last['note']}</i>"

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("🗑 Delete", callback_data=CB_DEL_CONFIRM),
        InlineKeyboardButton("↩️ Cancel", callback_data=CB_DEL_CANCEL),
    ]])
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)


async def delete_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query: CallbackQuery = update.callback_query
    await query.answer()

    if query.data == CB_DEL_CANCEL:
        await query.edit_message_text("↩️ Cancelled.")
        return

    deleted = storage.delete_last_transaction()
    if deleted is None:
        await query.edit_message_text("Nothing to delete.")
        return

    method_label = formatter.METHOD_LABELS.get(deleted.get("method", ""), deleted.get("method", ""))
    type_label = formatter.TYPE_LABELS.get(deleted.get("type", ""), deleted.get("type", ""))
    await query.edit_message_text(
        f"🗑 <b>Deleted</b>\n{type_label}  ·  {method_label}  ·  {deleted['category']}  ·  {deleted['amount']:,.0f}",
        parse_mode=ParseMode.HTML,
    )


# ---------------------------------------------------------------------------
# Category Management — conversation flow
# ---------------------------------------------------------------------------

async def categories_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await _check_auth(update):
        return ConversationHandler.END

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data=f"{CB_CAT_TYPE}:{key}")]
        for key, label in TYPE_LABELS.items()
    ])
    await update.message.reply_text(
        "⚙️ <b>Manage Categories</b>\n\nSelect type:",
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard,
    )
    return CAT_TYPE


async def cat_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query: CallbackQuery = update.callback_query
    await query.answer()

    tx_type = query.data.split(":")[1]
    context.user_data["cat_type"] = tx_type
    cats = storage.get_categories().get(tx_type, [])
    cats_list = "\n".join(f"  • {c}" for c in cats) if cats else "  (none)"

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Add", callback_data=f"{CB_CAT_ACTION}:add"),
            InlineKeyboardButton("🗑 Remove", callback_data=f"{CB_CAT_ACTION}:remove"),
        ],
        [InlineKeyboardButton("← Back", callback_data=f"{CB_CAT_ACTION}:back")],
    ])
    await query.edit_message_text(
        f"⚙️ <b>{TYPE_LABELS[tx_type]} Categories</b>\n\n<pre>{cats_list}</pre>",
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard,
    )
    return CAT_ACTION


async def cat_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query: CallbackQuery = update.callback_query
    await query.answer()

    action = query.data.split(":")[1]

    if action == "back":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(label, callback_data=f"{CB_CAT_TYPE}:{key}")]
            for key, label in TYPE_LABELS.items()
        ])
        await query.edit_message_text(
            "⚙️ <b>Manage Categories</b>\n\nSelect type:",
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
        )
        return CAT_TYPE

    if action == "add":
        await query.edit_message_text("Enter the name of the new category:")
        return CAT_ADD_NAME

    # action == "remove"
    tx_type = context.user_data.get("cat_type", "expense")
    cats = storage.get_categories().get(tx_type, [])
    if not cats:
        await query.edit_message_text("No categories to remove.")
        return ConversationHandler.END

    rows = [
        [InlineKeyboardButton(c, callback_data=f"{CB_CAT_REMOVE}:{c}") for c in cats[i:i + 3]]
        for i in range(0, len(cats), 3)
    ]
    await query.edit_message_text("Select category to remove:", reply_markup=InlineKeyboardMarkup(rows))
    return CAT_REMOVE_SELECT


async def cat_add_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.message.text.strip()[:50]
    tx_type = context.user_data.get("cat_type", "expense")

    if storage.add_category(tx_type, name):
        await update.message.reply_text(
            f"✅ Added <b>{name}</b> to {TYPE_LABELS[tx_type]} categories.",
            parse_mode=ParseMode.HTML,
            reply_markup=SETTINGS_KEYBOARD,
        )
    else:
        await update.message.reply_text(
            f"⚠️ <b>{name}</b> already exists.",
            parse_mode=ParseMode.HTML,
            reply_markup=SETTINGS_KEYBOARD,
        )
    context.user_data.clear()
    return ConversationHandler.END


async def cat_remove_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query: CallbackQuery = update.callback_query
    await query.answer()

    name = query.data.split(":", 1)[1]
    tx_type = context.user_data.get("cat_type", "expense")
    storage.remove_category(tx_type, name)

    await query.edit_message_text(
        f"🗑 Removed <b>{name}</b> from {TYPE_LABELS[tx_type]} categories.",
        parse_mode=ParseMode.HTML,
    )
    context.user_data.clear()
    return ConversationHandler.END


async def cat_cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("❌ Cancelled.", reply_markup=SETTINGS_KEYBOARD)
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# Scheduled jobs
# ---------------------------------------------------------------------------

async def scheduled_daily_report(context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = context.job.data["chat_id"]
    today_rows = storage.get_today()
    if not today_rows:
        return
    month_rows = storage.get_this_month()
    text = formatter.format_daily_report(today_rows, month_rows)
    await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.HTML)


async def scheduled_monthly_report(context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = context.job.data["chat_id"]
    now = datetime.now(TIMEZONE)
    last_day = calendar.monthrange(now.year, now.month)[1]
    if now.day != last_day:
        return
    this_rows = storage.get_this_month()
    if not this_rows:
        return
    last_rows = storage.get_last_month()
    text = formatter.format_monthly_report(this_rows, last_rows)
    await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.HTML)


async def scheduled_yearly_report(context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = context.job.data["chat_id"]
    now = datetime.now(TIMEZONE)
    if not (now.month == 12 and now.day == 31):
        return
    year_rows = storage.get_this_year()
    if not year_rows:
        return
    text = formatter.format_yearly_report(year_rows)
    await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.HTML)


# ---------------------------------------------------------------------------
# Application builder
# ---------------------------------------------------------------------------

def build_application(token: str, chat_id: str) -> Application:
    app = Application.builder().token(token).build()

    # Fallbacks shared across conversations: cancel + immediately process the new action
    nav_fallbacks = [
        CommandHandler("cancel", cancel_command),
        MessageHandler(filters.Regex(r"^📊 Summary$"), _interrupt(summary_command)),
        MessageHandler(filters.Regex(r"^📋 Reports$"), _interrupt(reports_menu)),
        MessageHandler(filters.Regex(r"^⚙️ Settings$"), _interrupt(settings_menu)),
        MessageHandler(filters.Regex(r"^📅 Today$"), _interrupt(report_today)),
        MessageHandler(filters.Regex(r"^📆 This Month$"), _interrupt(report_monthly)),
        MessageHandler(filters.Regex(r"^🗓 This Year$"), _interrupt(report_yearly)),
        MessageHandler(filters.Regex(r"^🏠 Main Menu$"), _interrupt(back_to_main)),
        # Cross-conversation: cancel current and return to main so user can re-press
        MessageHandler(filters.Regex(r"^📂 Categories$"), _interrupt(settings_menu)),
        MessageHandler(filters.Regex(r"^🗑 Delete Last$"), _interrupt(settings_menu)),
        MessageHandler(filters.Regex(r"^➕ Add Transaction$"), _interrupt(back_to_main)),
        MessageHandler(filters.Regex(r"^🕐 Recent$"), _interrupt(recent_command)),
    ]

    # Add Transaction conversation
    add_conv = ConversationHandler(
        entry_points=[
            CommandHandler("add", add_command),
            MessageHandler(filters.Regex(r"^➕ Add Transaction$"), add_command),
        ],
        states={
            SELECT_TYPE: [CallbackQueryHandler(select_type_callback, pattern=f"^{CB_TYPE}:")],
            SELECT_CATEGORY: [CallbackQueryHandler(select_category_callback, pattern=f"^{CB_CAT}:")],
            SELECT_METHOD: [CallbackQueryHandler(select_method_callback, pattern=f"^{CB_METHOD}:")],
            ENTER_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_amount_handler)],
            ENTER_NOTE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_note_handler),
                CallbackQueryHandler(skip_note_callback, pattern=f"^{CB_SKIP}$"),
            ],
            CONFIRM: [CallbackQueryHandler(confirm_callback, pattern=f"^({CB_CONFIRM}|{CB_CANCEL})$")],
        },
        fallbacks=nav_fallbacks,
    )

    # Category management conversation
    cat_conv = ConversationHandler(
        entry_points=[
            CommandHandler("categories", categories_command),
            MessageHandler(filters.Regex(r"^📂 Categories$"), categories_command),
        ],
        states={
            CAT_TYPE: [CallbackQueryHandler(cat_type_callback, pattern=f"^{CB_CAT_TYPE}:")],
            CAT_ACTION: [CallbackQueryHandler(cat_action_callback, pattern=f"^{CB_CAT_ACTION}:")],
            CAT_ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, cat_add_handler)],
            CAT_REMOVE_SELECT: [CallbackQueryHandler(cat_remove_callback, pattern=f"^{CB_CAT_REMOVE}:")],
        },
        fallbacks=[
            CommandHandler("cancel", cat_cancel_command),
            MessageHandler(filters.Regex(r"^📊 Summary$"), _interrupt(summary_command)),
            MessageHandler(filters.Regex(r"^📋 Reports$"), _interrupt(reports_menu)),
            MessageHandler(filters.Regex(r"^⚙️ Settings$"), _interrupt(settings_menu)),
            MessageHandler(filters.Regex(r"^📅 Today$"), _interrupt(report_today)),
            MessageHandler(filters.Regex(r"^📆 This Month$"), _interrupt(report_monthly)),
            MessageHandler(filters.Regex(r"^🗓 This Year$"), _interrupt(report_yearly)),
            MessageHandler(filters.Regex(r"^🏠 Main Menu$"), _interrupt(back_to_main)),
            MessageHandler(filters.Regex(r"^➕ Add Transaction$"), _interrupt(back_to_main)),
            MessageHandler(filters.Regex(r"^🗑 Delete Last$"), _interrupt(settings_menu)),
        ],
    )

    # Register handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(add_conv)
    app.add_handler(cat_conv)

    app.add_handler(CommandHandler("summary", summary_command))
    app.add_handler(MessageHandler(filters.Regex(r"^📊 Summary$"), summary_command))

    app.add_handler(MessageHandler(filters.Regex(r"^📋 Reports$"), reports_menu))
    app.add_handler(MessageHandler(filters.Regex(r"^📅 Today$"), report_today))
    app.add_handler(MessageHandler(filters.Regex(r"^📆 This Month$"), report_monthly))
    app.add_handler(MessageHandler(filters.Regex(r"^🗓 This Year$"), report_yearly))

    app.add_handler(MessageHandler(filters.Regex(r"^🕐 Recent$"), recent_command))
    app.add_handler(MessageHandler(filters.Regex(r"^⚙️ Settings$"), settings_menu))
    app.add_handler(MessageHandler(filters.Regex(r"^🗑 Delete Last$"), delete_last_handler))
    app.add_handler(MessageHandler(filters.Regex(r"^🏠 Main Menu$"), back_to_main))

    # Global callback for delete confirmation
    app.add_handler(CallbackQueryHandler(
        delete_confirm_callback,
        pattern=f"^({CB_DEL_CONFIRM}|{CB_DEL_CANCEL})$",
    ))

    # Scheduled jobs at 23:30 Bangkok time
    job_data = {"chat_id": chat_id}
    report_time = datetime.strptime("23:30", "%H:%M").replace(tzinfo=TIMEZONE).timetz()
    app.job_queue.run_daily(scheduled_daily_report, time=report_time, data=job_data, name="daily")
    app.job_queue.run_daily(scheduled_monthly_report, time=report_time, data=job_data, name="monthly")
    app.job_queue.run_daily(scheduled_yearly_report, time=report_time, data=job_data, name="yearly")

    return app
