import asyncio
import logging
import threading
import pyodbc
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from flask import Flask, redirect, render_template_string, request, url_for

# ==========================================
# 1. SETUP & CONFIGURATIONS
# ==========================================
TOKEN = "8666627485:AAGVdXvmME7UV7JmEpI3U563_aky3mrEGC4"
ADMIN_ID = 123456789  # <--- የአድሚን ቴሌግራም ID

conn_str = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=localhost;"
    "DATABASE=Alpha_car_db;"
    "Trusted_Connection=yes;"
)

bot = Bot(token=TOKEN)
dp = Dispatcher()
app = Flask(__name__)
app.secret_key = "alpha_cars_secret_key"


# FSM States
class RegistrationState(StatesGroup):
  full_name = State()
  phone_number = State()
  address = State()
  id_info = State()


class PaymentState(StatesGroup):
  waiting_for_receipt = State()


class MaintenanceState(StatesGroup):
  plate_number = State()
  repair_description = State()
  repair_cost = State()


# ==========================================
# 2. TELEGRAM BOT HANDLERS & COMMAND MENU
# ==========================================
async def set_bot_commands(bot: Bot):
  commands = [
      BotCommand(command="start", description="ቦቱን ለማስጀመር እና ሰላምታ"),
      BotCommand(command="cars", description="የሚገኙ መኪኖች ዝርዝር ማሳያ"),
      BotCommand(command="register", description="እንደ አዲስ ደንበኛ ለመመዝገብ"),
      BotCommand(command="pay", description="ክፍያ ለመፈጸም እና ቫውቸር ለመላክ"),
      BotCommand(command="maintenance", description="የጥገና መዝገብ ለመጨመር"),
      BotCommand(command="view_maintenance", description="የጥገና ታሪኮችን ለማየት"),
  ]
  await bot.set_my_commands(commands)


@dp.message(Command("start"))
async def send_welcome(message: types.Message):
  await message.answer(
      "ሰላም ቤቲ! እንኳን ወደ 'Alpha Cars' ማስተዳደሪያ ሲስተም በደህና መጡ። 🚀\n\n"
      "🔹 ከታች ያለውን **Menu** በመጫን ወይም ትእዛዞቹን በመጠቀም ሲስተሙን መቆጣጠር ትችላለህ።"
  )


@dp.message(Command("register"))
async def start_registration(message: types.Message, state: FSMContext):
  await state.set_state(RegistrationState.full_name)
  await message.answer(
      "እባክዎ የሙሉ ስምዎን ያስገቡ (ለምሳሌ፦ ከበደ መኮንን):"
  )


@dp.message(RegistrationState.full_name)
async def process_full_name(message: types.Message, state: FSMContext):
  name = message.text.strip()
  if len(name) < 3 or not any(c.isalpha() for c in name):
    await message.answer("❌ ስምዎ በጣም አጭር ነው ወይም ትክክለኛ ፊደላት አልያዘም።")
    return
  await state.update_data(full_name=name)
  await state.set_state(RegistrationState.phone_number)
  await message.answer(
      "እባክዎ ስልክ ቁጥርዎን ያስገቡ (በ 09 ወይም 07 የሚጀምር፣ 10 ዲጂት):"
  )


@dp.message(RegistrationState.phone_number)
async def process_phone(message: types.Message, state: FSMContext):
  phone = message.text.strip()
  if (
      not phone.isdigit()
      or len(phone) != 10
      or not (phone.startswith("09") or phone.startswith("07"))
  ):
    await message.answer(
        "❌ **የተሳሳተ ስልክ ቁጥር!** በ 09 ወይም 07 የሚጀምር 10 አሃዝ ቁጥር ብቻ ያስገቡ:"
    )
    return
  await state.update_data(phone_number=phone)
  await state.set_state(RegistrationState.address)
  await message.answer("እባክዎ የመኖሪያ አድራሻዎን ያስገቡ:")


@dp.message(RegistrationState.address)
async def process_address(message: types.Message, state: FSMContext):
  await state.update_data(address=message.text.strip())
  await state.set_state(RegistrationState.id_info)
  await message.answer("እባክዎ የመታወቂያ ወይም የፋይዳ ቁጥርዎን (ID/Fayda) ያስገቡ:")


@dp.message(RegistrationState.id_info)
async def process_id_info(message: types.Message, state: FSMContext):
  data = await state.get_data()
  try:
    conn = pyodbc.connect(conn_str, timeout=5)
    cursor = conn.cursor()
    cursor.execute(
        """
            INSERT INTO clients_registration (telegram_id, full_name, phone_number, address, id_info)
            VALUES (?, ?, ?, ?, ?)
        """,
        (
            str(message.from_user.id),
            data.get("full_name"),
            data.get("phone_number"),
            data.get("address"),
            message.text.strip(),
        ),
    )
    conn.commit()
    cursor.close()
    conn.close()
    await message.answer("✅ **ምዝገባዎ በስኬት ተጠናቋል!** አሁን `/pay` በመጠቀም ክፍያ መፈጸም ይችላሉ።")
  except Exception as e:
    await message.answer(f"ስህተት ተፈጥሯል: {e}")
  await state.clear()


@dp.message(Command("pay"))
async def start_payment(message: types.Message):
  keyboard = InlineKeyboardMarkup(
      inline_keyboard=[
          [
              InlineKeyboardButton(
                  text="🏦 የባንክ ዝውውር", callback_data="pay_bank"
              )
          ],
          [
              InlineKeyboardButton(
                  text="📱 ዲጂታል ክፍያ (Telebirr)", callback_data="pay_digital"
              )
          ],
          [InlineKeyboardButton(text="📜 ሲፒኦ (CPO)", callback_data="pay_cpo")],
      ]
  )
  await message.answer("💳 **እባክዎ የሚፈልጉትን የክፍያ አማራጭ ይምረጡ:**", reply_markup=keyboard)


@dp.callback_query(F.data.startswith("pay_"))
async def process_payment_choice(callback: types.CallbackQuery, state: FSMContext):
  methods = {
      "pay_bank": "የባንክ ዝውውር",
      "pay_digital": "ዲጂታል ክፍያ",
      "pay_cpo": "ሲፒኦ (CPO)",
  }
  method_name = methods.get(callback.data, "ሌላ")
  await state.update_data(payment_method=method_name)
  await state.set_state(PaymentState.waiting_for_receipt)
  await callback.message.answer(
      f"መረጡት፦ **{method_name}**\n📸 እባክዎ የክፍያ ማረጋገጫ (Receipt) ፎቶ ይላኩ:"
  )
  await callback.answer()


@dp.message(PaymentState.waiting_for_receipt, F.photo)
async def process_receipt_photo(message: types.Message, state: FSMContext):
  data = await state.get_data()
  payment_method = data.get("payment_method")
  telegram_id = str(message.from_user.id)
  photo_path = message.photo[-1].file_id

  try:
    conn = pyodbc.connect(conn_str, timeout=5)
    cursor = conn.cursor()
    cursor.execute(
        """
            INSERT INTO payments (telegram_id, payment_method, receipt_photo_path, payment_status)
            OUTPUT INSERTED.payment_id
            VALUES (?, ?, ?, 'Pending')
        """,
        (telegram_id, payment_method, photo_path),
    )
    payment_id = cursor.fetchone()[0]
    conn.commit()
    cursor.close()
    conn.close()

    await message.answer(
        "✅ **የክፍያ ማረጋገጫዎ ተቀብለናል!** አስተዳዳሪው እስኪያረጋግጠው ይጠብቁ።"
    )

    admin_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ አጽድቅ",
                    callback_data=f"admin_approve_{payment_id}_{telegram_id}",
                ),
                InlineKeyboardButton(
                    text="❌ ውድቅ",
                    callback_data=f"admin_reject_{payment_id}_{telegram_id}",
                ),
            ]
        ]
    )
    await bot.send_photo(
        chat_id=ADMIN_ID,
        photo=photo_path,
        caption=(
            f"🔔 **አዲስ ክፍያ!**\nደንበኛ ID: {telegram_id}\nክፍያ ID: {payment_id}"
        ),
        reply_markup=admin_keyboard,
    )
  except Exception as e:
    await message.answer(f"ስህተት ተፈጥሯል: {e}")
  await state.clear()


@dp.callback_query(F.data.startswith("admin_"))
async def handle_admin_decision(callback: types.CallbackQuery):
  _, action, payment_id, client_id = callback.data.split("_")
  status = "Approved" if action == "approve" else "Rejected"
  try:
    conn = pyodbc.connect(conn_str, timeout=5)
    cursor = conn.cursor()
    
    # 1. የክፍያ ሁኔታን ማዘመን
    cursor.execute(
        "UPDATE payments SET payment_status = ? WHERE payment_id = ?",
        (status, payment_id),
    )
    
    # 2. ክፍያው ከጸደቀ (Approved) የሚገኝ የመጀመሪያውን Available መኪና ወደ Sold መቀየር
    if status == "Approved":
      cursor.execute(
          "SELECT TOP 1 plate_number FROM cars_new WHERE status = 'Available'"
      )
      car = cursor.fetchone()
      if car:
        plate_to_sell = car[0]
        cursor.execute(
            "UPDATE cars_new SET status = 'Sold' WHERE plate_number = ?",
            (plate_to_sell,),
        )

    conn.commit()
    cursor.close()
    conn.close()

    msg = (
        "✅ ክፍያዎ ጸድቋል! መኪናዎ ተመድቧል።"
        if status == "Approved"
        else "❌ የክፍያ ጥያቄዎ ውድቅ ተደርጓል።"
    )
    await bot.send_message(client_id, msg)
    
    sold_note = "\n🚗 (መኪናው ወደ Sold ተዘምኗል)" if status == "Approved" else ""
    await callback.message.edit_caption(
        caption=f"{callback.message.caption}\n\nውሳኔ: {status}{sold_note}",
        reply_markup=None,
    )
    await callback.answer("ተመዝግቧል!")
  except Exception as e:
    await callback.answer(f"ስህተት: {e}", show_alert=True)


@dp.message(Command("cars"))
async def show_cars(message: types.Message):
  try:
    conn = pyodbc.connect(conn_str, timeout=5)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT make, model, year, price, status, plate_number FROM cars_new"
        " WHERE status = 'Available'"
    )
    cars = cursor.fetchall()
    if not cars:
      await message.answer("ይቅርታ! በአሁኑ ሰዓት የሚገኝ መኪና የለም።")
      return
    response = "🚗 **የ Alpha Cars መኪኖች ዝርዝር:**\n\n"
    for car in cars:
      response += (
          f"🔹 {car.make} {car.model} ({car.year})\n💰 ዋጋ: {car.price:,.2f}"
          f" ብር\n🔢 ሰሌዳ: {car.plate_number}\n-------------------\n"
      )
    await message.answer(response)
    cursor.close()
    conn.close()
  except Exception as e:
    await message.answer(f"ስህተት: {e}")


# ==========================================
# 3. FLASK ADMIN DASHBOARD (WEB PANEL)
# ==========================================
ADMIN_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Alpha Cars - Admin Dashboard</title>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; background: #f4f7f6; margin: 0; padding: 20px; }
        h2 { color: #333; }
        table { width: 100%; border-collapse: collapse; background: #fff; margin-bottom: 30px; }
        th, td { padding: 12px; border: 1px solid #ddd; text-align: left; }
        th { background-color: #007bff; color: white; }
    </style>
</head>
<body>
    <h2>🚗 Alpha Cars - Admin Panel</h2>
    
    <h3>📋 የተመዘገቡ ደንበኞች (Clients)</h3>
    <table>
        <tr><th>ID</th><th>ስም</th><th>ስልክ ቁጥር</th><th>አድራሻ</th><th>መታወቂያ/ፋይዳ</th></tr>
        {% for client in clients %}
        <tr><td>{{ client[0] }}</td><td>{{ client[2] }}</td><td>{{ client[3] }}</td><td>{{ client[4] }}</td><td>{{ client[5] }}</td></tr>
        {% endfor %}
    </table>

    <h3>💳 የክፍያ ታሪኮች (Payments)</h3>
    <table>
        <tr><th>ክፍያ ID</th><th>ቴሌግራም ID</th><th>የክፍያ መንገድ</th><th>ሁኔታ (Status)</th></tr>
        {% for pay in payments %}
        <tr><td>{{ pay[0] }}</td><td>{{ pay[1] }}</td><td>{{ pay[2] }}</td><td>{{ pay[4] }}</td></tr>
        {% endfor %}
    </table>
</body>
</html>
"""


@app.route("/")
def admin_dashboard():
  try:
    conn = pyodbc.connect(conn_str, timeout=5)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM clients_registration")
    clients = cursor.fetchall()
    cursor.execute(
        "SELECT payment_id, telegram_id, payment_method, receipt_photo_path,"
        " payment_status FROM payments"
    )
    payments = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template_string(
        ADMIN_TEMPLATE, clients=clients, payments=payments
    )
  except Exception as e:
    return f"የዳታቤዝ ስህተት: {e}"


def run_flask():
  app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)


# ==========================================
# 4. MAIN RUNNER (BOTH BOT & WEB RUN TOGETHER)
# ==========================================
async def main():
  flask_thread = threading.Thread(target=run_flask)
  flask_thread.daemon = True
  flask_thread.start()

  await set_bot_commands(bot)
  logging.info("Alpha Cars Bot & Admin Panel are running successfully!")
  await dp.start_polling(bot)


if __name__ == "__main__":
  logging.basicConfig(level=logging.INFO)
  asyncio.run(main())