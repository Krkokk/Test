import asyncio
import json
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command, Text
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

# === CONFIG ===
BOT_TOKEN = "8184432030:AAE-vcwzz_ydmSMOXuNmFjLpI5vI4Zy5Z0M"
ADMIN_IDS = [1443655356]  # Replace with your Telegram user ID(s)

# === STORAGE FILE ===
DATA_FILE = "data.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"users": {}, "balances": {}, "orders": {}}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

# === LOAD DATA ===
data = load_data()
users = data.get("users", {})
balances = data.get("balances", {})
orders = data.get("orders", {})

services = {}  # {category: [ {name, api, price, refill}, ... ]}
categories = []  # list of category names
descriptions = {}  # {service_name: description_text}

# === BOT INIT ===
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
    [KeyboardButton(text="طلب خدمة")],
    [KeyboardButton(text="الخدمات"), KeyboardButton(text="تتبع الطلبات")]
])

# === HANDLERS ===

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
            "مرحبًا بك في بوت فانتوم للرشق\n"
            "اقرأ وصف الخدمة قبل الطلب\n"
            "في حال واجهت اي مشكلة لا تتردد بمراسلة الدعم عن طريق امر /ticket",
            reply_markup=user_main_kb
        )

@dp.message(Command(commands=["ticket"]))
async def handle_ticket(message: types.Message):
    await message.answer(
        "ارسـل مشكلتك مع ارفاق سكرين شوت ( لقطة شاشة ) إن وجد، سيتم الرد عليك بواسطة الدعم الفني بأقرب وقت ممكن"
    )

@dp.message(Command(commands=["order"]))
async def order_by_id(message: types.Message):
    try:
        order_id = int(message.text.split(" ")[1])
    except (IndexError, ValueError):
        await message.answer("صيغة غير صحيحة. استخدم /order <رقم الطلب>")
        return
    user_orders = orders.get(str(message.from_user.id), [])
    for o in user_orders:
        if o["id"] == order_id:
            await message.answer(
                f"معلومات الطلب:\n"
                f"الرقم: {o['id']}\n"
                f"الخدمة: {o['service']}\n"
                f"الكمية: {o['quantity']}\n"
                f"السعر: {o['price']}$\n"
                f"الحالة: {o['status']}"
            )
            return
    await message.answer("لم يتم العثور على الطلب.")

@dp.message(Text("Stats"), F.from_user.id.in_(ADMIN_IDS))
async def show_stats(message: types.Message):
    total_users = len(users)
    total_orders = sum(len(orders.get(uid, [])) for uid in orders)
    total_money = sum(order["price"] for uid in orders for order in orders[uid])
    await message.answer(
        f"الإحصائيات:\n"
        f"عدد المستخدمين: {total_users}\n"
        f"عدد الطلبات: {total_orders}\n"
        f"المبلغ الإجمالي المصروف: {total_money:.2f}$"
    )

@dp.message(Text("Users"), F.from_user.id.in_(ADMIN_IDS))
async def view_users(message: types.Message):
    if not users:
        await message.answer("لا يوجد مستخدمون.")
        return
    msg = "قائمة المستخدمين:\n"
    for uid in users:
        msg += f"ID: {uid} | الرصيد: {balances.get(uid, 0):.2f}$\n"
    await message.answer(msg)

@dp.message(Text("All Orders"), F.from_user.id.in_(ADMIN_IDS))
async def view_all_orders(message: types.Message):
    output = "جميع الطلبات:\n"
    count = 0
    for uid, user_orders in orders.items():
        for o in user_orders:
            output += f"{o['service']} : {o['quantity']} : {uid}\n"
            count += 1
    if count == 0:
        await message.answer("لا توجد طلبات.")
    else:
        await message.answer(output)

# === ADD SERVICE FLOW ===

@dp.message(Text("Add Service"), F.from_user.id.in_(ADMIN_IDS))
async def add_service_start(message: types.Message, state: FSMContext):
    await message.answer("أرسل اسم التصنيف الذي تريد وضع الخدمة فيه:", reply_markup=ReplyKeyboardMarkup(
        resize_keyboard=True, keyboard=[[KeyboardButton(text="Cancel")]]
    ))
    await state.set_state(AddService.waiting_for_category)

@dp.message(AddService.waiting_for_category, F.text)
async def add_service_category(message: types.Message, state: FSMContext):
    if message.text.lower() == "cancel":
        await state.clear()
        await message.answer("تم الإلغاء.", reply_markup=admin_kb)
        return
    category = message.text.strip()
    if category not in services:
        services[category] = []
        categories.append(category)
    await state.update_data(category=category)
    await message.answer("أرسل اسم الخدمة:")
    await state.set_state(AddService.waiting_for_name)

@dp.message(AddService.waiting_for_name, F.text)
async def add_service_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("أرسل رابط API الخاص بالخدمة:")
    await state.set_state(AddService.waiting_for_api)

@dp.message(AddService.waiting_for_api, F.text)
async def add_service_api(message: types.Message, state: FSMContext):
    await state.update_data(api=message.text.strip())
    await message.answer("أرسل سعر الخدمة (مثال: 2.5):")
    await state.set_state(AddService.waiting_for_price)

@dp.message(AddService.waiting_for_price, F.text)
async def add_service_price(message: types.Message, state: FSMContext):
    try:
        price = float(message.text)
    except ValueError:
        await message.answer("من فضلك أدخل رقماً صحيحاً للسعر.")
        return
    await state.update_data(price=price)
    kb = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [KeyboardButton(text="Yes"), KeyboardButton(text="No")]
    ])
    await message.answer("هل هذه الخدمة تحتوي على ريفيل؟ (Yes / No)", reply_markup=kb)
    await state.set_state(AddService.waiting_for_refill)

@dp.message(AddService.waiting_for_refill, F.text)
async def add_service_refill(message: types.Message, state: FSMContext):
    data_state = await state.get_data()
    category = data_state["category"]
    name = data_state["name"]
    api = data_state["api"]
    price = data_state["price"]
    refill = "Refill working" if message.text.lower() == "yes" else "No refill"
    service_obj = {
        "name": name,
        "api": api,
        "price": price,
        "refill": refill
    }
    services[category].append(service_obj)
    descriptions[name] = refill
    await state.clear()
    await message.answer(f"✅ تم إضافة الخدمة '{name}' في التصنيف '{category}' مع الوصف: {refill}", reply_markup=admin_kb)

# === USER ORDER FLOW ===

@dp.message(Text("طلب خدمة"))
async def order_start(message: types.Message, state: FSMContext):
    if not categories:
        await message.answer("لا توجد خدمات متاحة حالياً.")
        return
    kb = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[[KeyboardButton(text=c)] for c in categories])
    await message.answer("اختر التصنيف:", reply_markup=kb)
    await state.set_state(OrderService.choosing_category)

@dp.message(OrderService.choosing_category, F.text)
async def choose_category(message: types.Message, state: FSMContext):
    category = message.text
    if category not in categories:
        await message.answer("التصنيف غير موجود، حاول مرة أخرى.")
        return
    await state.update_data(category=category)
    kb = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[[KeyboardButton(text=s["name"])] for s in services[category]])
    await message.answer("اختر الخدمة:", reply_markup=kb)
    await state.set_state(OrderService.choosing_service)

@dp.message(OrderService.choosing_service, F.text)
async def choose_service(message: types.Message, state: FSMContext):
    data_state = await state.get_data()
    category = data_state["category"]
    service_name = message.text
    service = next((s for s in services[category] if s["name"] == service_name), None)
    if not service:
        await message.answer("الخدمة غير موجودة، حاول مرة أخرى.")
        return
    await state.update_data(service=service)
    desc = descriptions.get(service_name, "")
    await message.answer(f"{service_name}\nالسعر لكل 1000 = {service['price']}$\nالوصف: {desc}\n\nأرسل الكمية المطلوبة:")
    await state.set_state(OrderService.entering_quantity)

@dp.message(OrderService.entering_quantity, F.text)
async def enter_quantity(message: types.Message, state: FSMContext):
    quantity_str = ''.join(filter(str.isdigit, message.text))
    if not quantity_str:
        await message.answer("من فضلك أدخل كمية صحيحة.")
        return
    quantity = int(quantity_str)
    data_state = await state.get_data()
    service = data_state["service"]
    total_price = (quantity / 1000) * service["price"]
    await state.update_data(quantity=quantity, total=total_price)

    buttons = [
        [InlineKeyboardButton(text="✅ Accept", callback_data="accept_order"),
         InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_order")]
    ]
    if service.get("refill") == "Refill working":
        buttons.append([InlineKeyboardButton(text="Refill", callback_data="refill_info")])
    inline_kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    await message.answer(
        f"السعر الكلي: {total_price:.2f}$\nهل تريد المتابعة؟",
        reply_markup=inline_kb
    )
    await state.set_state(OrderService.confirming)

@dp.callback_query(F.data == "accept_order")
async def accept_order(callback: types.CallbackQuery, state: FSMContext):
    user_id = str(callback.from_user.id)
    data_state = await state.get_data()

    order = {
        "id": len(orders.get(user_id, [])) + 1,
        "service": data_state["service"]["name"],
        "quantity": data_state["quantity"],
        "price": round(data_state["total"], 2),
        "status": "تم التنفيذ"
    }

    orders.setdefault(user_id, []).append(order)
    save_data({"users": users, "balances": balances, "orders": orders})

    await callback.message.edit_text(f"✅ تم تنفيذ الطلب بنجاح! (Order ID: {order['id']})")
    await state.clear()

@dp.callback_query(F.data == "cancel_order")
async def cancel_order(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("تم إلغاء الطلب.")
    await state.clear()

@dp.callback_query(F.data == "refill_info")
async def refill_info(callback: types.CallbackQuery):
    await callback.answer("هذه الخدمة تدعم الريفيل.", show_alert=True)

@dp.message(Text("الخدمات"))
async def list_services(message: types.Message):
    if not categories:
        await message.answer("لا توجد خدمات متاحة حالياً.")
        return
    text = "قائمة التصنيفات والخدمات:\n"
    for cat in categories:
        text += f"\n- {cat}:\n"
        for svc in services.get(cat, []):
            text += f"  • {svc['name']} - السعر لكل 1000: {svc['price']}$ - {svc['refill']}\n"
    await message.answer(text)

@dp.message(Text("تتبع الطلبات"))
async def track_orders(message: types.Message):
    user_id = str(message.from_user.id)
    user_orders = orders.get(user_id, [])
    if not user_orders:
        await message.answer("لا توجد طلبات حتى الآن.")
        return
    msg = "قائمة الطلبات:\n"
    for o in user_orders:
        msg += (
            f"\nطلب {o['id']}\n"
            f"الخدمة: {o['service']}\n"
            f"الكمية: {o['quantity']}\n"
            f"السعر: {o['price']}$\n"
            f"الحالة: {o['status']}\n"
        )
    await message.answer(msg)

# === RUN BOT ===
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())