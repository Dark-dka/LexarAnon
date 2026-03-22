"""
FSM states for admin panel flows (add channel, add bot).
"""
from aiogram.fsm.state import State, StatesGroup


class AddChannelFSM(StatesGroup):
    title = State()
    username = State()
    invite_link = State()
    confirm = State()


class AddBotFSM(StatesGroup):
    title = State()
    username = State()
    invite_link = State()
    confirm = State()
