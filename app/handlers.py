# handlers.py
import logging
from aiogram import Router, F
from aiogram.types import (
    ChatMemberUpdated, Message, CallbackQuery, PollAnswer,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)

from aiogram import Bot
import time
from aiogram.types import BotCommand
from aiogram.types import BotCommandScopeDefault
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

from .keyboards import quiz_size_keyboard, confirm_quiz_keyboard, end_quiz_keyboard
from .quiz_manager import QuizManager
from .states import QuizCreation
from . import db  # db.get_groups, db.save_group, db.add_result, db.get_leaderboard

logger = logging.getLogger(__name__)
router = Router()
quiz_manager = QuizManager()


# ----------------------------
# Safe send helpers
# ----------------------------
async def safe_send_message(bot, chat_id, text, **kwargs):
    try:
        return await bot.send_message(chat_id, text, **kwargs)
    except (TelegramForbiddenError, TelegramBadRequest):
        logger.warning(f"⚠️ Bot bu chatga yozolmadi: {chat_id}")
    except Exception as e:
        logger.exception("send_message xato: %s", e)

async def safe_send_poll(bot, chat_id, **kwargs):
    try:
        return await bot.send_poll(chat_id, **kwargs)
    except (TelegramForbiddenError, TelegramBadRequest):
        logger.warning(f"⚠️ Bot bu chatga poll yuborolmadi: {chat_id}")
    except Exception as e:
        logger.exception("send_poll xato: %s", e)

async def safe_answer(message: Message, text: str, **kwargs):
    try:
        return await message.answer(text, **kwargs)
    except (TelegramForbiddenError, TelegramBadRequest):
        logger.warning(f"⚠️ Bot foydalanuvchiga javob bera olmadi: {message.chat.id}")
    except Exception as e:
        logger.exception("message.answer xato: %s", e)


# ----------------------------
# Helper / Keyboards
# ----------------------------
def add_to_group_keyboard(bot_username: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Botni guruhga qo‘shish", url=f"https://t.me/{bot_username}?startgroup=true")]
    ])


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Yangi viktorina")],
            [KeyboardButton(text="📊 Reyting")],
            [KeyboardButton(text="➕ Guruhga qo‘shish")],
            [KeyboardButton(text="❌ Bekor qilish")]
        ],
        resize_keyboard=True
    )


def groups_inline_keyboard(groups: list[tuple[int, str]], prefix: str = "choose_group") -> InlineKeyboardMarkup:
    kb = []
    for gid, title in groups:
        name = title or f"ID {gid}"
        kb.append([InlineKeyboardButton(text=name, callback_data=f"{prefix}:{gid}")])
    return InlineKeyboardMarkup(inline_keyboard=kb)



# ----------------------------
# (qolgan handlerlaring shu yerda o‘zgarishsiz, faqat .answer / .send_message / .send_poll
# joylari safe_* funksiyalariga o‘zgartirildi)
# Masalan:
# await message.answer("matn")  ->  await safe_answer(message, "matn")
# await bot.send_message(chat_id, "matn") -> await safe_send_message(bot, chat_id, "matn")
# await bot.send_poll(chat_id=gid, question=..., options=...) -> await safe_send_poll(bot, gid, question=..., options=...)
# ----------------------------




# Buttons/texts that should NOT be treated as "option" when creating quiz
MENU_TEXTS = {"➕ Guruhga qo‘shish", "📋 Yangi viktorina", "📊 Reyting", "❌ Bekor qilish", "/menu", "/cancel", "/start"}


# ----------------------------
# /start & /menu
# ----------------------------

processed_events = {}

@router.message(Command("start"))
async def start_cmd(message: Message):
    me = await message.bot.get_me()

    # Agar guruh yoki supergroup bo‘lsa, faqat ma'lumot beramiz, lekin xabar yuborishni my_chat_member ga qoldiramiz
    if message.chat.type in ("group", "supergroup"):
        # Check if this is a fresh group addition
        event_key = f"{message.chat.id}:start:{message.date}"
        if event_key in processed_events and time() - processed_events[event_key] < 5:
            logger.debug(f"Ignoring duplicate /start in chat {message.chat.id}")
            return
        processed_events[event_key] = time.time()

        # Let my_chat_member handle the "bot added" message
        return

    # Faqat private chat bo‘lsa menyuni ko‘rsatamiz
    user_id = message.from_user.id
    try:
        groups = db.get_groups(user_id) or []
    except Exception:
        g = db.get_group(user_id)
        groups = [g] if g else []

    if not groups:
        await safe_answer(
            message,
            "Salom 👋 CyberQuizBot ga xush kelibsiz!\n\n"
            "❗ Avval botni guruhga qo‘shing va uni admin qiling, keyin viktorina yaratishingiz mumkin.",
            reply_markup=add_to_group_keyboard(me.username)
        )
    else:
        await safe_answer(
            message,
            "✅ Bot ulangan! Asosiy menyu:",
            reply_markup=main_menu_keyboard()
        )


@router.message(Command("menu"))
async def menu_cmd(message: Message):
    # Guruhlarda menyu chiqmasin
    if message.chat.type in ("group", "supergroup"):
        await message.answer(
            "❌ Bu buyruq guruhda ishlamaydi.\n"
            "📩 Botga shaxsiy yozib menyudan foydalanishingiz mumkin."
        )
        return

    # Faqat private chatda menyu chiqadi
    await message.answer("📍 Asosiy menyu", reply_markup=main_menu_keyboard())



# ----------------------------
# '➕ Guruhga qo‘shish' reply-button pressed
# ----------------------------
@router.message(F.text == "➕ Guruhga qo‘shish")
async def handle_add_group_text(message: Message):
    """If user pressed the reply-button (which only sends a text), reply with an inline URL keyboard."""
    me = await message.bot.get_me()
    await message.answer(
        "Botni guruhga qo‘shish uchun quyidagi tugmani bosing:",
        reply_markup=add_to_group_keyboard(me.username)
    )


@router.message(F.text == "📋 Yangi viktorina")
async def new_quiz_from_menu(message: Message, state: FSMContext):
    """Start new quiz: only in private chat."""

    # ❌ Agar guruh bo‘lsa to‘xtatamiz
    if message.chat.type != "private":
        await message.answer("❌ Viktorinani faqat bot bilan shaxsiy chatda yaratishingiz mumkin.")
        return

    user_id = message.from_user.id
    me = await message.bot.get_me()

    try:
        groups = db.get_groups(user_id) or []
    except Exception:
        g = db.get_group(user_id)
        groups = [g] if g else []

    if not groups:
        await message.answer(
            "❌ Siz hali hech qanday guruhga botni qo‘shmagansiz.\n\n"
            "➕ Avval botni guruhga qo‘shing:",
            reply_markup=add_to_group_keyboard(me.username)
        )
        return

    # 🔧 Har bir guruh uchun title olish
    group_list: list[tuple[int, str]] = []
    for g in groups:
        group_id = g[0] if isinstance(g, tuple) else g
        try:
            chat = await message.bot.get_chat(group_id)
            group_list.append((group_id, chat.title))
        except Exception:
            group_list.append((group_id, None))  # fallback

    if not group_list:
        await message.answer("❌ Hech qaysi guruh nomini olish imkonsiz bo‘ldi.")
        return

    if len(group_list) == 1:
        gid, title = group_list[0]
        await state.update_data(group_id=gid)
        await message.answer(
            f"✅ Guruh avtomatik tanlandi: <b>{title or gid}</b>\n\n"
            "Endi nechta savoldan iborat viktorina tuzmoqchisiz?",
            reply_markup=quiz_size_keyboard()
        )
        return

    # Multiple groups -> tanlash
    await message.answer(
        "📌 Qaysi guruh uchun viktorina yaratmoqchisiz?",
        reply_markup=groups_inline_keyboard(group_list, prefix="choose_group")
    )





@router.callback_query(F.data.startswith("choose_group:"))
async def choose_group_callback(callback: CallbackQuery, state: FSMContext):
    try:
        group_id = int(callback.data.split(":", 1)[1])
    except Exception:
        await callback.answer("❌ Noto‘g‘ri guruh tanlandi.", show_alert=True)
        return

    await state.update_data(group_id=group_id)
    await callback.message.answer(
        "✅ Guruh tanlandi!\nEndi nechta savoldan iborat viktorina tuzmoqchisiz?",
        reply_markup=quiz_size_keyboard()
    )
    await callback.answer()



async def set_bot_commands(bot: Bot):
    # Faqat private chat uchun komandalarni o‘rnatamiz
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Botni ishga tushirish"),
            BotCommand(command="menu", description="Asosiy menyu"),
            BotCommand(command="rating", description="Reytingni ko‘rish"),
            BotCommand(command="cancel", description="Viktorinani bekor qilish"),
        ],
        scope=BotCommandScopeDefault()
    )


# ----------------------------
# Bot added to group / admin status change notification
# ----------------------------
@router.my_chat_member()
async def on_bot_my_chat_member(event: ChatMemberUpdated):
    bot = event.bot
    new_status = event.new_chat_member.status
    old_status = event.old_chat_member.status if event.old_chat_member else None
    chat = event.chat
    inviter = event.from_user

    # Create a unique key for this event
    event_key = f"{chat.id}:{new_status}:{event.date}"
    if event_key in processed_events and time.time() - processed_events[event_key] < 5:
        logger.debug(f"Ignoring duplicate event: {event_key}")
        return
    processed_events[event_key] = time.time()


    # Log the event for debugging
    logger.info(
        f"ChatMemberUpdated: chat={chat.id} ({chat.title}), "
        f"new_status={new_status}, old_status={old_status}, inviter={inviter.id}"
    )

    # Handle bot added as member (only if transitioning to 'member' status)
    if new_status == "member" and old_status != "member":
        await safe_send_message(
            bot,
            chat.id,
            "🤖 Bot guruhga qo‘shildi, lekin ishlamaydi.\n\n"
            "⚠️ Botni ADMIN qiling va keyin botga qaytib shaxsiy chatda viktorina yaratib, guruhga yuboring."
        )
        # Save group to DB with title
        try:
            db.save_group(inviter.id, chat.id, chat.title)
        except Exception as e:
            logger.exception(f"DB.save_group xato (chat={chat.id}): {e}")

    # Handle bot promoted to admin
    elif new_status == "administrator" and old_status != "administrator":
        # Send confirmation to the group
        await safe_send_message(
            bot,
            chat.id,
            "✅ Bot guruhga ulandi va ADMIN qilindi!\n\n"
            "🎯 Endi bot bilan shaxsiy chatda viktorina yaratib, guruhga yuborishingiz mumkin."
        )

        # Send confirmation to the inviter (in private chat)
        if inviter and not inviter.is_bot:
            try:
                await safe_send_message(
                    bot,
                    inviter.id,
                    "✅ Guruh muvaffaqiyatli ulandi va bot ADMIN qilindi!\n\n"
                    "Asosiy menyudan yangi viktorina yarating:",
                    reply_markup=main_menu_keyboard()
                )
            except Exception as e:
                logger.exception(f"Inviterga xabar yuborilmadi (user={inviter.id}): {e}")

        # Save group to DB with title
        try:
            db.save_group(inviter.id, chat.id, chat.title)
        except Exception as e:
            logger.exception(f"DB.save_group xato (chat={chat.id}): {e}")

    # Handle bot removed from group
    elif new_status == "left":
        logger.info(f"Bot guruhdan chiqarildi: {chat.title} (chat_id={chat.id})")
        # Optionally, remove group from DB
        try:
            db.remove_group(chat.id)  # Assuming you have a remove_group function
        except Exception as e:
            logger.exception(f"DB.remove_group xato (chat={chat.id}): {e}")

    # Ignore other status changes to prevent duplicate messages
    else:
        logger.debug(f"Ignored status change: {old_status} -> {new_status} in chat {chat.id}")


@router.callback_query(F.data.startswith("quiz_size:"))
async def choose_quiz_size(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    size = int(callback.data.split(":", 1)[1])

    data = await state.get_data()
    group_id = data.get("group_id")

    if not group_id:
        try:
            groups = db.get_groups(user_id) or []
        except Exception:
            g = db.get_group(user_id)
            groups = [g] if g else []

        if not groups:
            me = await callback.bot.get_me()
            await callback.message.answer(
                "❌ Guruh topilmadi. Avval botni guruhga qo‘shing va uni admin qiling.",
                reply_markup=add_to_group_keyboard(me.username)
            )
            await callback.answer()
            return

        if len(groups) > 1:
            group_list = []
            for g in groups:
                gid = g[0] if isinstance(g, tuple) else g
                try:
                    chat = await callback.bot.get_chat(gid)
                    group_list.append((gid, chat.title))
                except Exception:
                    group_list.append((gid, None))

            await callback.message.answer(
                "❗ Iltimos, qaysi guruhga viktorina yuborishni xohlaysiz?",
                reply_markup=groups_inline_keyboard(group_list, prefix="choose_group")
            )
            await callback.answer()
            return

        group_id = groups[0][0] if isinstance(groups[0], tuple) else groups[0]

    # ✅ quiz yaratish — bu yer endi hamma holda ishlaydi
    quiz_id = quiz_manager.start_quiz(user_id, group_id, size)
    await state.update_data(group_id=group_id, quiz_id=quiz_id)
    await state.set_state(QuizCreation.waiting_for_question)

    # ⚡️ Guruhga e’lon yuborish
    try:
        await callback.bot.send_message(
            chat_id=group_id,
            text=(
                f"👋 Assalomu alaykum, viktorina qatnashchilari!\n\n"
                f"🎯 Biz {size} talik viktorinani boshladik.\n"
                "❗ Savollarga tayyor bo‘ling!"
            )
        )
    except Exception as e:
        print(f"Guruhga e’lon yuborilmadi: {e}")

    await callback.message.answer(
        f"📋 {size} ta savollik viktorina boshlaymiz.\n📝 Savolni yuboring (shaxsiy chatda)."
    )

    await callback.answer()




# ----------------------------
# Question / Options flow
# ----------------------------
@router.message(QuizCreation.waiting_for_question)
async def get_question(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text:
        await message.answer("❌ Iltimos matn yuboring.")
        return

    # reject menu texts as questions
    if text in MENU_TEXTS:
        await message.answer("❗ Bu menyu tugmasi. Agar savol yubormoqchi bo'lsangiz haqiqiy matn yuboring.")
        return

    await state.update_data(question=text, options=[])
    await state.set_state(QuizCreation.waiting_for_options)
    await message.answer(
        "🔢 Variantlarni yuboring (har birini alohida xabarda).\n"
        "✅ Tugatgach /done deb yozing. Va undan keyin to'g'ri javobni tanlaysiz."
    )


@router.message(QuizCreation.waiting_for_options)
async def get_options(message: Message, state: FSMContext):
    text = (message.text or "").strip()

    if not text:
        await message.answer("❌ Bo‘sh xabar qabul qilinmaydi.")
        return

    # If user pressed the "➕ Guruhga qo‘shish" reply-button during option entry,
    # show the inline URL keyboard instead of treating it as an option.
    if text == "➕ Guruhga qo‘shish":
        me = await message.bot.get_me()
        await message.answer("Botni guruhga qo‘shish uchun tugmani bosing:", reply_markup=add_to_group_keyboard(me.username))
        return

    # If other menu texts — warn user to exit creation if they want to use menu
    if text in {"📋 Yangi viktorina", "📊 Reyting", "❌ Bekor qilish", "/menu", "/cancel"}:
        await message.answer("🚫 Siz hozir viktorina yaratish jarayonidasiz. Agar menyuga qaytmoqchi bo'lsangiz /cancel bilan chiqib qayting.")
        return

    if text.startswith("/") and text != "/done":
        await message.answer("❌ Noto‘g‘ri komanda! Variant sifatida faqat matn yuboring yoki /done deb tugating.")
        return

    if text == "/done":
        return await finish_options(message, state)

    data = await state.get_data()
    options = data.get("options", [])
    options.append(text)
    await state.update_data(options=options)
    await message.answer(f"➕ Variant qo‘shildi: {text}\n({len(options)} ta variant bor) \n/done deb tugatishingiz mumkin.")


async def finish_options(message: Message, state: FSMContext):
    data = await state.get_data()
    options = data.get("options", []) or []

    if len(options) < 2:
        await message.answer("❌ Kamida 2 ta variant bo‘lishi kerak!")
        return

    await state.set_state(QuizCreation.waiting_for_correct_answer)
    options_text = "\n".join([f"{i}. {opt}" for i, opt in enumerate(options)])
    await message.answer(
        f"🔽 Variantlar:\n{options_text}\n\nEndi to‘g‘ri javob raqamini yuboring (0 dan boshlab)."
    )


@router.message(QuizCreation.waiting_for_correct_answer)
async def get_correct_answer(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    try:
        correct_index = int(text)
    except ValueError:
        await message.answer("❌ Faqat raqam yuboring (variant raqamini).")
        return

    data = await state.get_data()
    question = data.get("question")
    options = data.get("options", [])
    group_id = data.get("group_id")
    quiz_id = data.get("quiz_id")

    if question is None or options is None:
        await message.answer("❌ Savol topilmadi. Iltimos qayta boshlang.")
        await state.clear()
        return

    if correct_index < 0 or correct_index >= len(options):
        await message.answer("❌ Noto‘g‘ri raqam! Variantlar oralig‘ida raqam kiriting.")
        return

    ok = quiz_manager.add_question(group_id, question, options, correct_index)
    if not ok:
        await message.answer("❌ Savol qo‘shishda xato. Avval viktorina boshlang (/menu va tanlang).")
        await state.clear()
        return

    if quiz_manager.is_quiz_ready(group_id):
        await state.clear()
        await message.answer("✅ Barcha savollar kiritildi!\nEndi tasdiqlaysizmi?", reply_markup=confirm_quiz_keyboard())
    else:
        quiz = quiz_manager.get_quiz(group_id)
        q_left = quiz["size"] - len(quiz["questions"])
        await state.set_state(QuizCreation.waiting_for_question)
        await message.answer(f"✅ Savol qo‘shildi. Yana {q_left} ta savol kerak.\n📝 Yangi savolni yuboring:")


# ----------------------------
# Confirm and send polls to group
# ----------------------------
@router.callback_query(F.data == "quiz:confirm")
async def confirm_quiz(callback: CallbackQuery):
    user_id = callback.from_user.id

    # Try to determine group_id: prefer active quiz owned by user
    group_id = None
    # search active_quizzes for owner's quiz
    for gid, q in quiz_manager.active_quizzes.items():
        if q.get("owner") == user_id:
            group_id = gid
            break

    # fallback to user's single group (if still None)
    if not group_id:
        try:
            groups = db.get_groups(user_id) or []
        except Exception:
            g = db.get_group(user_id)
            groups = [g] if g else []

        if len(groups) == 1:
            group_id = groups[0]

    if not group_id:
        me = await callback.bot.get_me()
        await callback.message.answer(
            "❌ Guruh topilmadi. Avval botni guruhga qo‘shing va uni admin qiling.",
            reply_markup=add_to_group_keyboard(me.username)
        )
        await callback.answer()
        return

    quiz = quiz_manager.get_quiz(group_id)
    if not quiz:
        await callback.message.answer("❌ Bu guruh uchun aktiv viktorina topilmadi.")
        await callback.answer()
        return

    if quiz.get("owner") != user_id:
        await callback.message.answer("❌ Faqat quiz egasi viktorinani guruhga yuborishi mumkin.")
        await callback.answer()
        return

    bot = callback.bot
    for i, q in enumerate(quiz["questions"]):
        try:
            poll_msg = await bot.send_poll(
                chat_id=group_id,
                question=q["question"],
                options=q["options"],
                type="quiz",
                correct_option_id=q["correct_index"],
                is_anonymous=False
            )
            quiz_manager.set_poll_id(group_id, i, poll_msg.poll.id)
        except Exception as e:
            logger.exception("Poll yuborishda xato (savol %s): %s", i, e)

    try:
        await bot.send_message(group_id, "✅ Viktorina boshlandi!\n\n⏳ Savollar tugagach, tugatish tugmasini bosing.", reply_markup=end_quiz_keyboard())
    except Exception as e:
        logger.exception("Guruhga boshlash xabari yuborilmadi: %s", e)

    await callback.message.answer("📤 Viktorina guruhga yuborildi!\n\n🆕 Yangi viktorina tuzish uchun /menu")
    try:
        await callback.message.edit_reply_markup()
    except Exception:
        pass
    await callback.answer()


# ----------------------------
# Poll answers handler
# ----------------------------
@router.poll_answer()
async def handle_poll_answer(poll_answer: PollAnswer):
    user_id = poll_answer.user.id
    option_ids = poll_answer.option_ids or []
    poll_id = poll_answer.poll_id

    for group_id, quiz in quiz_manager.active_quizzes.items():
        for q in quiz["questions"]:
            if q.get("poll_id") == poll_id:
                quiz_id = quiz.get("quiz_id")
                is_correct = (len(option_ids) == 1 and option_ids[0] == q["correct_index"])
                try:
                    success = db.add_result(quiz_id, user_id, group_id, is_correct)
                    if not success:
                        logger.error("Natija DB ga saqlanmadi: quiz_id=%s, user_id=%s", quiz_id, user_id)
                except Exception as e:
                    logger.exception("DB.add_result xato: %s", e)
                return


# ----------------------------
# End quiz (admin only)
# ----------------------------
@router.callback_query(F.data == "quiz:end")
@router.message(Command("endquiz"))
async def end_quiz(event):
    if isinstance(event, CallbackQuery):
        group_id = event.message.chat.id
        bot = event.bot
        user_id = event.from_user.id
    else:
        group_id = event.chat.id
        bot = event.bot
        user_id = event.from_user.id

    try:
        member = await bot.get_chat_member(group_id, user_id)
        if member.status not in ("creator", "administrator"):
            await bot.send_message(group_id, "❌ Faqat admin viktorinani tugatishi mumkin.")
            return
    except Exception as e:
        logger.exception("get_chat_member xato: %s", e)
        await bot.send_message(group_id, "❌ A'zo ma'lumotini olishda xato yuz berdi.")
        return

    quiz = quiz_manager.get_quiz(group_id)
    if not quiz:
        await bot.send_message(group_id, "❌ Bu guruh uchun aktiv viktorina topilmadi.")
        return

    quiz_id = quiz.get("quiz_id")
    leaderboard = db.get_leaderboard(quiz_id, group_id, limit=50)

    if not leaderboard:
        await bot.send_message(group_id, "📊 Hali hech kim qatnashmadi.")
        quiz_manager.clear_quiz(group_id)
        return

    total_players = len(leaderboard)
    text = f"🏁 Viktorina yakunlandi!\n\n👥 Qatnashchilar soni: {total_players}\n\n"

    for i, row in enumerate(leaderboard, start=1):
        uid, correct, total = row
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        try:
            user_obj = await bot.get_chat(uid)
            display_name = f"@{user_obj.username}" if user_obj.username else \
                (user_obj.first_name + (" " + user_obj.last_name if user_obj.last_name else "")).strip() or str(uid)
        except Exception:
            display_name = str(uid)
        text += f"{medal} <a href='tg://user?id={uid}'>{display_name}</a> — {correct}/{total} ball\n"

    await bot.send_message(group_id, text, parse_mode="HTML")
    quiz_manager.clear_quiz(group_id)


# ----------------------------
# Show rating / leaderboard
# ----------------------------
@router.message(Command("rating"))
@router.message(Command("reyting"))
@router.message(F.text == "📊 Reyting")
async def show_rating_cmd(message: Message):
    bot = message.bot

    # Guruhda yozilgan bo‘lsa -> shu guruh uchun ko‘rsatamiz
    if message.chat.type in ("group", "supergroup"):
        group_id = message.chat.id
        quiz = quiz_manager.get_quiz(group_id)
        quiz_id = quiz.get("quiz_id") if quiz else None

        if not quiz_id:
            await message.answer("❌ Aktiv viktorina topilmadi.")
            return

        leaderboard = db.get_leaderboard(quiz_id, group_id, limit=10)
        if not leaderboard:
            await message.answer("📊 Hali hech kim qatnashmadi.")
            return

        text = "🏆 Viktorina reytingi:\n\n"
        for i, row in enumerate(leaderboard, start=1):
            uid, correct, total = row
            try:
                user_obj = await bot.get_chat(uid)
                display_name = f"@{user_obj.username}" if user_obj.username else \
                    (user_obj.first_name + (" " + user_obj.last_name if user_obj.last_name else "")).strip() or str(uid)
            except Exception:
                display_name = str(uid)

            text += f"{i}. <a href='tg://user?id={uid}'>{display_name}</a> — {correct}/{total} ball\n"

        await message.answer(text, parse_mode="HTML")
        return

    # Shaxsiy chat -> foydalanuvchi guruh tanlashi kerak
    user_id = message.from_user.id
    try:
        groups = db.get_groups(user_id) or []
    except Exception:
        g = db.get_group(user_id)
        groups = [g] if g else []

    if not groups:
        me = await bot.get_me()
        await message.answer(
            "❌ Sizda saqlangan guruh yo‘q.\n\n➕ Avval botni guruhga qo‘shing:",
            reply_markup=add_to_group_keyboard(me.username)
        )
        return

    # faqat 1 ta guruh bo‘lsa -> avtomatik ko‘rsatamiz
    if len(groups) == 1:
        gid = groups[0][0] if isinstance(groups[0], tuple) else groups[0]
        quiz = quiz_manager.get_quiz(gid)
        quiz_id = quiz.get("quiz_id") if quiz else None

        if not quiz_id:
            await message.answer("❌ Ushbu guruh uchun aktiv viktorina topilmadi.")
            return

        leaderboard = db.get_leaderboard(quiz_id, gid, limit=10)
        if not leaderboard:
            await message.answer("📊 Hali hech kim qatnashmadi.")
            return

        text = "🏆 Viktorina reytingi:\n\n"
        for i, row in enumerate(leaderboard, start=1):
            uid, correct, total = row
            try:
                user_obj = await bot.get_chat(uid)
                display_name = f"@{user_obj.username}" if user_obj.username else \
                    (user_obj.first_name + (" " + user_obj.last_name if user_obj.last_name else "")).strip() or str(uid)
            except Exception:
                display_name = str(uid)

            text += f"{i}. <a href='tg://user?id={uid}'>{display_name}</a> — {correct}/{total} ball\n"

        await message.answer(text, parse_mode="HTML")
        return

    # bir nechta guruh bo‘lsa -> foydalanuvchiga tanlash uchun ro‘yxat chiqaramiz
    group_list = []
    for g in groups:
        gid = g[0] if isinstance(g, tuple) else g
        try:
            chat = await bot.get_chat(gid)
            group_list.append((gid, chat.title))
        except Exception:
            group_list.append((gid, None))

    await message.answer(
        "📌 Qaysi guruhning reytingini ko‘rmoqchisiz?",
        reply_markup=groups_inline_keyboard(group_list, prefix="show_rating")
    )



@router.callback_query(F.data.startswith("show_rating:"))
async def show_rating_callback(callback: CallbackQuery):
    try:
        gid = int(callback.data.split(":", 1)[1])
    except Exception:
        await callback.answer("Noto'g'ri guruh.", show_alert=True)
        return

    quiz = quiz_manager.get_quiz(gid)
    quiz_id = quiz.get("quiz_id") if quiz else None
    if not quiz_id:
        await callback.message.answer("❌ Ushbu guruh uchun aktiv viktorina topilmadi.")
        await callback.answer()
        return

    leaderboard = db.get_leaderboard(quiz_id, gid, limit=10)
    if not leaderboard:
        await callback.message.answer("📊 Hali hech kim qatnashmadi.")
        await callback.answer()
        return

    text = "🏆 Viktorina reytingi:\n\n"
    for i, row in enumerate(leaderboard, start=1):
        uid, correct, total = row
        try:
            user_obj = await callback.bot.get_chat(uid)
            display_name = f"@{user_obj.username}" if user_obj.username else \
                (user_obj.first_name + (" " + user_obj.last_name if user_obj.last_name else "")).strip() or str(uid)
        except Exception:
            display_name = str(uid)
        text += f"{i}. <a href='tg://user?id={uid}'>{display_name}</a> — {correct}/{total} ball\n"

    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()


# ----------------------------
# Cancel handlers
# ----------------------------
@router.callback_query(F.data == "quiz:cancel")
async def cancel_quiz(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id

    try:
        groups = db.get_groups(user_id) or []
    except Exception:
        g = db.get_group(user_id)
        groups = [g] if g else []

    if groups:
        for gid, _ in groups:
            quiz_manager.clear_quiz(gid)

    try:
        await callback.message.answer("❌ Viktorina bekor qilindi.")
        await callback.message.edit_reply_markup()
    except Exception:
        pass

    await state.clear()
    await callback.answer()


@router.message(Command("cancel"))
@router.message(F.text == "❌ Bekor qilish")
async def cancel_creation(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    try:
        groups = db.get_groups(user_id) or []
    except Exception:
        g = db.get_group(user_id)
        groups = [g] if g else []
    if groups:
        for gid in groups:
            quiz_manager.clear_quiz(gid)

    await message.answer("❌ Viktorina bekor qilindi.", reply_markup=main_menu_keyboard())


# ----------------------------
# Debug fallback (for testing)
# ----------------------------
@router.message()
async def debug_all_messages(message: Message):
    logger.debug(f"foydalanuvchi yubordi: {message.text}")
    # await safe_answer(message, "Men bu xabarni ushladim, lekin unga maxsus handler yozilmagan 👀")
