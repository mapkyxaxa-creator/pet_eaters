from aiogram.fsm.state import State, StatesGroup


class PetCreationStates(StatesGroup):
    """Состояния для создания питомца"""
    waiting_for_photo = State()
    waiting_for_name = State()