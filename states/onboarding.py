from aiogram.fsm.state import State, StatesGroup


class OnboardingStates(StatesGroup):
    """Состояния для онбординга"""
    step_1_adventure = State()
    step_2_feed = State()
    step_3_profile = State()
    step_4_social = State()
    step_5_house = State()
    step_6_final = State()
