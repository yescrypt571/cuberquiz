from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def start_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Guruhga qo‘shish", url="https://t.me/YourBot?startgroup=true")]
        ],
        resize_keyboard=True
    )


def end_quiz_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⏹ Viktorinani tugatish", callback_data="quiz:end")]
        ]
    )


def quiz_size_keyboard():
    buttons = []
    for i in range(5, 55, 5):
        buttons.append([InlineKeyboardButton(text=f"{i} ta", callback_data=f"quiz_size:{i}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def quiz_size_keyboard():
    sizes = [2, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50]
    buttons = [
        [InlineKeyboardButton(text=f"{size} ta", callback_data=f"quiz_size:{size}")]
        for size in sizes
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def answer_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ To‘g‘ri", callback_data="answer:correct"),
         InlineKeyboardButton(text="❌ Noto‘g‘ri", callback_data="answer:wrong")]
    ])

def confirm_quiz_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Ha, guruhga yubor", callback_data="quiz:confirm")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="quiz:cancel")]
    ])
def menu_keyboard(bot_username: str):
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Yangi viktorina")],
            [KeyboardButton(text="➕ Guruhga qo‘shish", url=f"https://t.me/{bot_username}?startgroup=true")],
            [KeyboardButton(text="📊 Reyting"), KeyboardButton(text="❌ Bekor qilish")],
        ],
        resize_keyboard=True
    )
