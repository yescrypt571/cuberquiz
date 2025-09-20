from aiogram.fsm.state import StatesGroup, State

class QuizCreation(StatesGroup):
    waiting_for_question = State()
    waiting_for_options = State()
    waiting_for_correct_answer = State()
