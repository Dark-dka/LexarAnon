"""
FSM states for admin panel flows (add channel, add bot, add campaign).
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


class AddCampaignFSM(StatesGroup):
    name = State()
    description = State()
    code = State()
