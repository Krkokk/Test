import asyncio
import json
import os
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command, Text
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

# === CONFIG ===
BOT_TOKEN = "8184432030:AAE-vcwzz_ydmSMOXuNmFjLpI5vI4Zy5Z0M"
ADMIN_IDS = [1443655356]

DATA_FILE = "data.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"users": {}, "balances": {}, "orders": {}}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

data = load_data()
users = data.get("users", {})
balances = data.get("balances", {})
orders = data.get("orders", {})

services = {}  # {category: [{name, api, price, refill}]}
categories = []  # list of category names
descriptions = {}  # {service_name: description}

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(storage=MemoryStorage())

# === FSM STATES ===
class AddService(StatesGroup):
    waiting_for_category = State()
    waiting_for_name = State()
    waiting_for_api = State()
    waiting_for_price = State()
    waiting_for_refill = State()

class OrderService(StatesGroup):
    choosing_category = State()
    choosing_service = State()
    entering_quantity = State()
    confirming = State()

class Ticket(StatesGroup):
    waiting_for_ticket_message = State()

# === KEYBOARDS ===
admin_kb = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
    [KeyboardButton(text="Add Service"), KeyboardButton(text="Add Description")],
    [KeyboardButton(text="Remove Service"), KeyboardButton(text="Add Category")],
    [KeyboardButton(text="Add Funds"), KeyboardButton(text="Remove Funds")],
    [KeyboardButton(text="Add Admin ID")],
    [KeyboardButton(text="Users"), KeyboardButton(text="All Orders")],
    [KeyboardButton(text="Stats")]
])

user_main_kb = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
    [KeyboardButton(text="Order Service")],
    [KeyboardButton(text="Services"), KeyboardButton(text="Track Orders")]
])

# === START MESSAGE ===
@dp.message(CommandStart())
async def start(message: types.Message):
    user_id = str(message.from_user.id)
    if user_id not in users:
        users[user_id] = {}
        balances[user_id] = 0.0
        save_data({"users": users, "balances": balances, "orders": orders})

    if int(user_id) in ADMIN_IDS:
        await message.answer("Welcome Admin. Choose an action:", reply_markup=admin_kb)
    else:
        await message.answer(
            "Welcome to Phantom SMM Bot.\n"
            "Please read the service description before ordering.\n"
            "If you face any issues, contact support using /ticket.",
            reply_markup=user_main_kb
        )

# === SUPPORT TICKET COMMAND ===
@dp.message(Command(commands=["ticket"]))
async def ticket_start(message: types.Message, state: FSMContext):
    await message.answer("Please describe your issue and attach a screenshot if available.")
    await Ticket.waiting_for_ticket_message.set()

@dp.message(Ticket.waiting_for_ticket_message)
async def ticket_forward(message: types.Message, state: FSMContext):
    # Forward user message to all admins
    for admin_id in ADMIN_IDS:
        try:
            await bot.forward_message(admin_id, message.from_user.id, message.message_id)
        except Exception as e:
            print(f"Failed to forward ticket to admin {admin_id}: {e}")
    await message.answer("Your message has been sent to the support team. They will reply as soon as possible.")
    await state.clear()

# === Admin Handlers ===

@dp.message(Text("Add Category"))
async def add_category(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer("Send the name of the category you want to add:")
    await AddService.waiting_for_category.set()

@dp.message(AddService.waiting_for_category)
async def receive_category(message: types.Message, state: FSMContext):
    category = message.text
    if category not in categories:
        categories.append(category)
    await state.update_data(category=category)
    await message.answer("Send the service name:")
    await AddService.waiting_for_name.set()

@dp.message(AddService.waiting_for_name)
async def receive_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Send the API or source of this service:")
    await AddService.waiting_for_api.set()

@dp.message(AddService.waiting_for_api)
async def receive_api(message: types.Message, state: FSMContext):
    await state.update_data(api=message.text)
    await message.answer("Send the price per 1000 units (e.g. 2.5):")
    await AddService.waiting_for_price.set()

@dp.message(AddService.waiting_for_price)
async def receive_price(message: types.Message, state: FSMContext):
    try:
        price = float(message.text)
    except:
        await message.answer("Please enter a valid number for the price.")
        return
    await state.update_data(price=price)
    await message.answer("Does this service support refill? (yes/no):")
    await AddService.waiting_for_refill.set()

@dp.message(AddService.waiting_for_refill)
async def receive_refill(message: types.Message, state: FSMContext):
    refill = message.text.lower() in ["yes", "y"]
    data = await state.get_data()
    service = {
        "name": data["name"],
        "api": data["api"],
        "price": data["price"],
        "refill": refill
    }
    category = data["category"]
    if category not in services:
        services[category] = []
    services[category].append(service)
    refill_note = "Refill working" if refill else "No refill"
    descriptions[service["name"]] = refill_note
    await message.answer(f"✅ Service '{service['name']}' added under '{category}' with {refill_note}")
    await state.clear()

@dp.message(Text("Add Description"))
async def add_description(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer("Send the service name you want to add a description for:")
    await AddService.waiting_for_name.set()

@dp.message(AddService.waiting_for_name)
async def receive_description(message: types.Message, state: FSMContext):
    service_name = message.text
    await state.update_data(description_service=service_name)
    await message.answer("Send the description text:")
    await AddService.waiting_for_api.set()

@dp.message(AddService.waiting_for_api)
async def receive_description_text(message: types.Message, state: FSMContext):
    desc = message.text
    data = await state.get_data()
    service_name = data.get("description_service")
    if service_name:
        descriptions[service_name] = desc
        await message.answer(f"✅ Description for '{service_name}' updated.")
    else:
        await message.answer("Service name not found in context.")
    await state.clear()

@dp.message(Text("Remove Service"))
async def remove_service_start(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    all_services = []
    for cat_services in services.values():
        all_services.extend([s["name"] for s in cat_services])
    if not all_services:
        await message.answer("No services to remove.")
        return
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.keyboard = [[KeyboardButton(s)] for s in all_services]
    await message.answer("Choose the service to remove:", reply_markup=kb)
    await AddService.waiting_for_name.set()

@dp.message(AddService.waiting_for_name)
async def remove_service_confirm(message: types.Message, state: FSMContext):
    service_name = message.text
    removed = False
    for cat in list(services.keys()):
        services[cat] = [s for s in services[cat] if s["name"] != service_name]
        if not services[cat]:
            del services[cat]
        else:
            removed = True
    if removed:
        descriptions.pop(service_name, None)
        await message.answer(f"✅ Service '{service_name}' removed.")
    else:
        await message.answer("Service not found.")
    await state.clear()

@dp.message(Text("Add Funds"))
async def add_funds(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer("Send user ID to add funds:")
    await AddService.waiting_for_category.set()

@dp.message(AddService.waiting_for_category)
async def add_funds_user(message: types.Message, state: FSMContext):
    user_id = message.text
    if user_id not in users:
        await message.answer("User not found.")
        return
    await state.update_data(user_id=user_id)
    await message.answer("Send amount to add:")
    await AddService.waiting_for_name.set()

@dp.message(AddService.waiting_for_name)
async def add_funds_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text)
    except:
        await message.answer("Enter a valid number.")
        return
    data = await state.get_data()
    user_id = data.get("user_id")
    balances[user_id] = balances.get(user_id, 0) + amount
    save_data({"users": users, "balances": balances, "orders": orders})
    await message.answer(f"✅ Added {amount}$ to user {user_id}.")
    await state.clear()

@dp.message(Text("Remove Funds"))
async def remove_funds(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer("Send user ID to remove funds:")
    await AddService.waiting_for_category.set()

@dp.message(AddService.waiting_for_category)
async def remove_funds_user(message: types.Message, state: FSMContext):
    user_id = message.text
    if user_id not in users:
        await message.answer("User not found.")
        return
    await state.update_data(user_id=user_id)
    await message.answer("Send amount to remove:")
    await AddService.waiting_for_name.set()

@dp.message(AddService.waiting_for_name)
async def remove_funds_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text)
    except:
        await message.answer("Enter a valid number.")
        return
    data = await state.get_data()
    user_id = data.get("user_id")
    balances[user_id] = balances.get(user_id, 0) - amount
    if balances[user_id] < 0:
        balances[user_id] = 0
    save_data({"users": users, "balances": balances, "orders": orders})
    await message.answer(f"✅ Removed {amount}$ from user {user_id}.")
    await state.clear()

@dp.message(Text("Add Admin ID"))
async def add_admin(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer("Send the new admin ID (user ID):")

@dp.message()
async def add_admin_id(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        new_admin_id = int(message.text)
    except:
        return
    if new_admin_id not in ADMIN_IDS:
        ADMIN_IDS.append(new_admin_id)
        await message.answer(f"✅ Added new admin: {new_admin_id}")
    else:
        await message.answer("This user is already an admin.")

# === User order flow ===

@dp.message(Text("Services"))
async def show_services(message: types.Message):
    if not categories:
        await message.answer("No categories available.")
        return
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.keyboard = [[KeyboardButton(c)] for c in categories]
    await message.answer("Choose a category:", reply_markup=kb)
    await OrderService.choosing_category.set()

@dp.message(OrderService.choosing_category)
async def choosing_service(message: types.Message, state: FSMContext):
    category = message.text
    if category not in services:
        await message.answer("Invalid category.")
        return
    await state.update_data(category=category)
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.keyboard = [[KeyboardButton(s["name"])] for s in services[category]]
    await message.answer("Choose a service:", reply_markup=kb)
    await OrderService.choosing_service.set()

@dp.message(OrderService.choosing_service)
async def entering_quantity(message: types.Message, state: FSMContext):
    service_name = message.text
    data = await state.get_data()
    category = data["category"]
    service = next((s for s in services[category] if s["name"] == service_name), None)
    if not service:
        await message.answer("Invalid service.")
        return
    await state.update_data(service=service)
    desc = descriptions.get(service_name, "")
    await message.answer(f"{service_name}, price per 1000: {service['price']}$\n{desc}\nSend quantity to order:")
    await OrderService.entering_quantity.set()

@dp.message(OrderService.entering_quantity)
async def confirm_order(message: types.Message, state: FSMContext):
    try:
        qty = int(message.text)
    except:
        await message.answer("Please enter a valid number.")
        return
    await state.update_data(quantity=qty)
    data = await state.get_data()
    total_price = round((qty / 1000) * data["service"]["price"], 2)
    await state.update_data(price=total_price)
    markup = InlineKeyboardMarkup
