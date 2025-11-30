import discord
from discord import app_commands
import random
import os
import sqlite3
import json
import asyncio

# --- CONFIGURATION ---
TOKEN = os.getenv('DISCORD_TOKEN') 
TARGET_URL = "https://roleplayth.com/showthread.php?tid="
ADMIN_ID = 432415629245415426  # ID ของ Matthew (Admin)
DB_NAME = "iceberg_data.db"    # ชื่อไฟล์ฐานข้อมูล

# --- DATABASE FUNCTIONS ---
def init_db():
    """สร้างตารางในฐานข้อมูลถ้ายังไม่มี"""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        # สร้างตาราง: user_id (PK), attempts (จำนวนครั้ง), completed (เสร็จยัง), links (เก็บลิงก์เป็น JSON String)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS players (
                user_id INTEGER PRIMARY KEY,
                attempts INTEGER DEFAULT 0,
                completed INTEGER DEFAULT 0,
                links TEXT DEFAULT '[]'
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS snowflakes (
                user_id INTEGER PRIMARY KEY,
                count INTEGER DEFAULT 0,
                completed INTEGER DEFAULT 0,
                links TEXT DEFAULT '[]'
            )
        ''')
        conn.commit()

def get_player(user_id):
    """ดึงข้อมูลผู้เล่นจาก DB"""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT attempts, completed, links FROM players WHERE user_id = ?", (user_id,))
        return cursor.fetchone() # คืนค่า (attempts, completed, links) หรือ None

def create_player(user_id, link):
    """สร้างผู้เล่นใหม่"""
    with sqlite3.connect(DB_NAME) as conn:
        links_json = json.dumps([link]) # แปลง list เป็น string เพื่อเก็บใน DB
        conn.execute("INSERT INTO players (user_id, attempts, completed, links) VALUES (?, 0, 0, ?)", (user_id, links_json))

def update_player_progress(user_id, attempts, completed, links_list):
    """อัปเดตข้อมูลผู้เล่น"""
    with sqlite3.connect(DB_NAME) as conn:
        links_json = json.dumps(links_list)
        conn.execute("UPDATE players SET attempts = ?, completed = ?, links = ? WHERE user_id = ?", 
                     (attempts, 1 if completed else 0, links_json, user_id))

def delete_player(user_id):
    """ลบผู้เล่น (Reset)"""
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("DELETE FROM players WHERE user_id = ?", (user_id,))

def get_all_players():
    """ดึงข้อมูลทุกคนสำหรับ Admin"""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, attempts, completed FROM players")
        return cursor.fetchall()

def get_snow_player(user_id):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT count, completed, links FROM snowflakes WHERE user_id = ?", (user_id,))
        return cursor.fetchone()

def create_snow_player(user_id, link):
    with sqlite3.connect(DB_NAME) as conn:
        links_json = json.dumps([link])
        conn.execute("INSERT INTO snowflakes (user_id, count, completed, links) VALUES (?, 0, 0, ?)", (user_id, links_json))

def update_snow_progress(user_id, count, completed, links_list):
    with sqlite3.connect(DB_NAME) as conn:
        links_json = json.dumps(links_list)
        conn.execute("UPDATE snowflakes SET count = ?, completed = ?, links = ? WHERE user_id = ?", 
                     (count, 1 if completed else 0, links_json, user_id))

# --- BOT SETUP ---
class MyClient(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)

    async def on_ready(self):
        init_db() # สร้างฐานข้อมูลเมื่อบอทเริ่มทำงาน
        await self.tree.sync()
        print(f'Logged in as {self.user} (Iceberg is ready with SQLite!)')

client = MyClient()

iceberg_group = app_commands.Group(name="iceberg", description="มาทุบน้ำแข็งกับข้า! Iceberg")

# --- CLASS ปุ่มกดสำหรับเกมจับหิมะ ---
class SnatchView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=3.0) # มีเวลาให้กดแค่ 3 วินาทีหลังจากปุ่มโผล่
        self.user_id = user_id
        self.clicked = False

    @discord.ui.button(label="❄️ คว้าเลย!", style=discord.ButtonStyle.success)
    async def grab_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("ไม่ใช่เกมของเอ็ง อย่ามาแย่ง!", ephemeral=True)
            return
        
        self.clicked = True
        button.disabled = True
        button.label = "คว้าทัน!"
        await interaction.response.edit_message(view=self)
        self.stop()

# ==========================================
# ⛄ COMMAND 1: /iceberg start
# ==========================================
@iceberg_group.command(name="start", description="ส่งลิงก์รับภารกิจเพื่อเริ่มทุบน้ำแข็ง")
@app_commands.describe(link="วางลิงก์โพสต์ที่โรลเพลย์รับภารกิจ")
async def start(interaction: discord.Interaction, link: str):
    user_id = interaction.user.id
    player = get_player(user_id)
    
    # เช็คว่าเคยเริ่มหรือยัง (ดูจาก DB)
    if player:
        await interaction.response.send_message("⛄ **Iceberg:** โอ๊ยย! เอ็งลงชื่อไปแล้วนี่หว่า จะเริ่มใหม่อีกกี่รอบ? ไปใช้คำสั่ง `/iceberg submit` เพื่อทุบน้ำแข็งนู่น!", ephemeral=True)
        return

    # เช็คลิงก์
    if not link.startswith(TARGET_URL):
        await interaction.response.send_message(f"⛄ **Iceberg:** ลิงก์อะไรเนี่ย? ข้าไม่รับ! ไปเอาลิงก์โพสต์ที่ถูกต้องมาส่งซะดีๆ", ephemeral=True)
        return

    # บันทึกข้อมูลลง DB
    create_player(user_id, link)
    
    embed = discord.Embed(
        title="⛄ Iceberg: \"หึ! กล้าดีนี่เจ้ามนุษย์...\"",
        description=(
            f"รับทราบ! รับปากแล้วนะว่าจะทุบ ทุบ ทุบ!\n"
            "แต่บอกไว้ก่อนนะว่าก้อนน้ำแข็งมันแข็งงงงงงมาก!\n\n"
            "**ภารกิจต่อจากนี้:**\n"
            "1. ไปโรลเพลย์ทุบน้ำแข็ง หรือหาทางทำลายมัน\n"
            "2. เอาลิงก์โพสต์มาส่งด้วยคำสั่ง `/iceberg submit`\n"
            "3. ส่งมาเรื่อยๆ จนกว่ามันจะแตก... ถ้ามีความพยายามพออะนะ ฮ่าๆๆ!"
        ),
        color=0xa5f3fc 
    )
    embed.set_thumbnail(url="https://media.tenor.com/t2akJIhYv6QAAAAM/skibidi-snowmen.gif")
    await interaction.response.send_message(embed=embed)


# ==========================================
# 🔨 COMMAND 2: /iceberg submit
# ==========================================
@iceberg_group.command(name="submit", description="ส่งลิงก์โรลเพลย์เพื่อทุบน้ำแข็ง")
@app_commands.describe(link="วางลิงก์โพสต์ที่นี่")
async def submit(interaction: discord.Interaction, link: str):
    user_id = interaction.user.id
    player = get_player(user_id) # ดึงข้อมูล: (attempts, completed, links_string)
    
    # Check Logic
    if not player:
        await interaction.response.send_message("⛄ **Iceberg:** เดี๋ยวก่อน! เห็นนะว่ายังไม่ได้ลงชื่อรับภารกิจเลย พิมพ์ `/iceberg start` พร้อมแนบลิงก์แรกมาก่อนเส้!", ephemeral=True)
        return
    
    attempts, completed, links_str = player
    links_list = json.loads(links_str) # แปลง JSON string กลับเป็น Python List
    
    if completed:
        await interaction.response.send_message("⛄ **Iceberg:** พอได้แล้วโว้ย! มันแตกไปแล้ว จะทุบให้ตายเลยรึไง? ไปเรียกแมทธิวมารับเรื่องไป๊!", ephemeral=True)
        return
    if not link.startswith(TARGET_URL):
        await interaction.response.send_message(f"⛄ **Iceberg:** ลิงก์มั่วอีกละ! ไปเอาลิงก์โพสต์ดี ๆ มา!", ephemeral=True)
        return
    if link in links_list:
        await interaction.response.send_message("⛄ **Iceberg:** ลิงก์นี้ทุบไปแล้ว! อย่ามาลักไก่ ไปโรลเพลย์มาใหม่เดี๋ยวนี้!", ephemeral=True)
        return

    # Process
    links_list.append(link)
    new_attempts = attempts + 1
    
    # RNG System
    bonus = 10 if new_attempts > 5 else 0
    chance = random.randint(1, 100) + bonus
    
    is_success = False

    # --- กรณีสำเร็จ (SUCCESS) ---
    if chance > 80: 
        is_success = True
        update_player_progress(user_id, new_attempts, True, links_list) # บันทึกว่าเสร็จแล้วลง DB
        
        success_msg = (
            f"🎉 **ยอมแล้วววววววววววว**\n"
            f"ทุบอยู่ได้ รำคาญโว้ยยยยยย!\n"
            f"เอ้า! รับรางวัลไปเจ้ามนุษย์ <@{user_id}>\n\n"
            f"📢 **เห้ยลูกพี่ <@{ADMIN_ID}> (Matthew)!**\n"
            f"มาดูผลงานเร็ววว ข้าจะไปนอนต่อละ!"
        )
        
        embed = discord.Embed(
            title="🧊 เพล้งงงง! น้ำแข็งแตกกระจาย!",
            description=success_msg,
            color=0x4ade80
        )
        embed.set_image(url="https://iili.io/fqqod4S.png")
        
        await interaction.response.send_message(content=f"<@{user_id}> <@{ADMIN_ID}>", embed=embed)

    # --- กรณีล้มเหลว (FAIL) ---
    else:
        update_player_progress(user_id, new_attempts, False, links_list) # บันทึกความคืบหน้าลง DB

        taunts = [
            "🥱 **Iceberg:** ฮ้าววว... ตีแรงได้แค่นี้เหรอ? ยายข้างบ้านยังตีแรงกว่าเลย",
            "🤣 **Iceberg:** ทุบหรือลูบ? น้ำแข็งข้ายังไม่รู้สึกอะไรเลยเนี่ย",
            "🧊 **Iceberg:** บิ่นไปนิดนึง... นิดเดียวจริงๆ แบบต้องใช้กล้องจุลทรรศน์ส่องอะ",
            "🤥 **Iceberg:** เหมือนจะได้นะ... (เสียงสูง) แต่ก็ไม่ได้ว่ะ ฮ่าๆๆ!",
            "🥶 **Iceberg:** มือแข็งล่ะสิ? ไปผิงไฟก่อนไหมน้อง แล้วค่อยมาใหม่",
            "🔨 **Iceberg:** เสียงดังฟังชัด แต่ดาเมจเป็นศูนย์! พยายามเข้านะจ๊ะ",
            "👀 **Iceberg:** มองหน้าทำไม? ก็มันไม่แตกอะ จะให้บอกว่าแตกได้ไง?"
        ]
        chosen_taunt = random.choice(taunts)

        embed = discord.Embed(
            title=f"💥 โป๊ก! (ความพยายามครั้งที่ {new_attempts})",
            description=chosen_taunt + "\n\n*อย่าเพิ่งท้อนะไอ้หนู ไปโรลมาใหม่!*",
            color=0xef4444
        )
        await interaction.response.send_message(embed=embed)


# ==========================================
# 📋 COMMAND 3: /iceberg check (Admin Only)
# ==========================================
@iceberg_group.command(name="check", description="[Admin] เช็คสถานะลูกลูกน้องทั้งหมด")
async def check_status(interaction: discord.Interaction):
    if interaction.user.id != ADMIN_ID:
        await interaction.response.send_message("⛄ **Iceberg:** ยุ่งน่า! ข้าให้ดูแค่เจ้านาย Matthew คนเดียวเว้ย!", ephemeral=True)
        return

    players = get_all_players() # ดึงข้อมูลทั้งหมดจาก DB

    if not players:
        await interaction.response.send_message("📂 **Report:** เงียบกริบ... ยังไม่มีใครกล้ามาแหยมกับข้าเลยลูกพี่", ephemeral=True)
        return

    report = "**📊 รายงานสถานะ Iceberg Mission (SQLite)**\n-----------------------------------\n"
    count_success = 0
    
    for row in players:
        # row = (user_id, attempts, completed)
        uid, attempts, completed = row
        status_icon = "✅ แตกแล้ว" if completed else "🔨 กำลังนัว"
        user_mention = f"<@{uid}>"
        report += f"• {user_mention} : ทุบ {attempts} ครั้ง [{status_icon}]\n"
        
        if completed: count_success += 1
    
    report += f"\n-----------------------------------\n👥 ทั้งหมด: {len(players)} คน | 🎉 สำเร็จ: {count_success} คน"
    
    embed = discord.Embed(description=report, color=0xfacc15)
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ==========================================
# 🔄 COMMAND 4: /iceberg reset (Admin Only)
# ==========================================
@iceberg_group.command(name="reset", description="[Admin] รีเซ็ตคนกากให้เริ่มใหม่")
@app_commands.describe(member="เลือกคนที่จะรีเซ็ต")
async def reset_user(interaction: discord.Interaction, member: discord.Member):
    if interaction.user.id != ADMIN_ID:
        await interaction.response.send_message("❌ ไม่ใช่แอดมินห้ามยุ่ง!", ephemeral=True)
        return

    # เช็คก่อนว่ามีไหม
    player = get_player(member.id)
    if player:
        delete_player(member.id) # ลบจาก DB
        await interaction.response.send_message(f"♻️ **Iceberg:** จัดไปครับลูกพี่! ลบข้อมูลเจ้า {member.mention} ออกจาก Database แล้ว ให้มันมาเริ่มใหม่ตั้งแต่ต้นเลย!", ephemeral=True)
    else:
        await interaction.response.send_message(f"⚠️ **Iceberg:** หาไม่เจอว่ะครับ {member.mention} มันเคยมาเล่นด้วยเหรอ?", ephemeral=True)

# Add Group เข้าสู่ Tree
client.tree.add_command(iceberg_group)

# ==================================================================
# ❄️ NEW GROUP: SNOWFLAKE SNATCHER (เกมคว้าเกล็ดหิมะ)
# ==================================================================
snow_group = app_commands.Group(name="snowflake", description="ภารกิจคว้าเกล็ดหิมะ (ต้องเก็บให้ครบ 5 ชิ้น)")

# 1. เริ่มต้นภารกิจ
@snow_group.command(name="start", description="รับภารกิจสะสมเกล็ดหิมะ")
@app_commands.describe(link="วางลิงก์โพสต์แรกเพื่อเริ่มงาน")
async def snow_start(interaction: discord.Interaction, link: str):
    user_id = interaction.user.id
    player = get_snow_player(user_id)

    if player:
        await interaction.response.send_message("❄️ **Matthew:** คุณรับงานนี้ไปแล้วครับ เริ่มสะสมด้วยคำสั่ง `/snowflake snatch` ได้เลย", ephemeral=True)
        return
    if not link.startswith(TARGET_URL):
        await interaction.response.send_message(f"❌ ลิงก์ไม่ถูกต้องครับ", ephemeral=True)
        return

    create_snow_player(user_id, link)
    
    embed = discord.Embed(
        title="❄️ ภารกิจ: Snowflake Collector",
        description=(
            f"สวัสดีคุณ **{interaction.user.name}** ผมต้องการ **เกล็ดหิมะสมบูรณ์ 5 ชิ้น**\n"
            "มันจะตกลงมาเร็วมาก คุณต้องตาไวหน่อยนะ\n\n"
            "**วิธีเล่น:**\n"
            "1. โรลเพลย์เดินหาจุดที่หิมะตก\n"
            "2. มาพิมพ์ `/snowflake snatch [ลิงก์]`\n"
            "3. รอจังหวะ... พอปุ่มสีเขียวเด้งขึ้นมา ให้รีบกด **'คว้าเลย!'** ให้ทัน\n"
            "4. ทำให้ครบ 5 ครั้ง แล้วมารรับรางวัล"
        ),
        color=0xffffff
    )
    await interaction.response.send_message(embed=embed)

# 2. เล่นเกมคว้าหิมะ
@snow_group.command(name="snatch", description="ส่งลิงก์แล้วรอกดปุ่มคว้าหิมะ!")
@app_commands.describe(link="วางลิงก์โรลเพลย์ล่าสุด")
async def snow_snatch(interaction: discord.Interaction, link: str):
    user_id = interaction.user.id
    player = get_snow_player(user_id) # (count, completed, links)

    # --- Check Logic ---
    if not player:
        await interaction.response.send_message("⚠️ รับภารกิจก่อนครับ พิมพ์ `/snowflake start`", ephemeral=True)
        return
    
    count, completed, links_str = player
    links_list = json.loads(links_str)

    if completed:
        await interaction.response.send_message("🎉 คุณเก็บครบ 5 ชิ้นไปแล้วครับ! พักผ่อนเถอะ", ephemeral=True)
        return
    if not link.startswith(TARGET_URL):
        await interaction.response.send_message("❌ ลิงก์ผิดครับ", ephemeral=True)
        return
    if link in links_list:
        await interaction.response.send_message("⚠️ ลิงก์ซ้ำ! ต้องโรลเพลย์ใหม่นะครับ", ephemeral=True)
        return

    # --- Game Start ---
    # ใช้ defer เพราะเกมนี้ต้องรอนานกว่า 3 วินาที (รอจังหวะหลอก)
    await interaction.response.defer() 

    # 1. ข้อความหลอกล่อ
    embed_wait = discord.Embed(title="👀 กำลังเพ่งมองท้องฟ้า...", description="รอก่อนนะ... อย่าเพิ่งกะพริบตา...", color=0x95a5a6)
    original_msg = await interaction.followup.send(embed=embed_wait)

    # 2. สุ่มเวลาหน่วง (2-5 วินาที)
    await asyncio.sleep(random.uniform(2, 5))

    # 3. ปุ่มโผล่!
    view = SnatchView(user_id)
    embed_now = discord.Embed(title="❄️ ร่วงลงมาแล้ว!!", description="**กดปุ่มเดี๋ยวนี้!!**", color=0x2ecc71)
    await interaction.edit_original_response(embed=embed_now, view=view)

    # 4. รอผลการกด (Wait for view to stop or timeout)
    await view.wait()

    # --- สรุปผล ---
    if view.clicked:
        # ชนะ: อัปเดตข้อมูล
        links_list.append(link)
        new_count = count + 1
        is_finished = (new_count >= 5)
        
        update_snow_progress(user_id, new_count, is_finished, links_list)

        if is_finished:
            # เก็บครบ 5 อัน
            embed_win = discord.Embed(
                title="💎 MISSION COMPLETE!",
                description=(
                    f"สุดยอด! คุณคว้าเกล็ดหิมะครบ **5/5 ชิ้น** แล้ว!\n"
                    f"ยินดีด้วยครับ <@{user_id}>\n\n"
                    f"📢 <@{ADMIN_ID}> มารับของหน่อยครับ!"
                ),
                color=0xf1c40f
            )
            embed_win.set_image(url="https://i.imgur.com/example_snow_collection.png") # เปลี่ยนรูปรวมได้
            await interaction.followup.send(content=f"<@{user_id}> <@{ADMIN_ID}>", embed=embed_win)
        else:
            # เก็บได้แต่ยังไม่ครบ
            await interaction.followup.send(
                f"✅ **คว้าทัน!** (สะสม: {new_count}/5)\n"
                f"เก่งมาก! รีบไปโรลเพลย์หาชิ้นต่อไป แล้วกลับมาใหม่นะ"
            )
    else:
        # แพ้ (กดไม่ทัน / หมดเวลา)
        await interaction.followup.send(
            f"💨 **ว้า... หายไปแล้ว**\n"
            f"คุณช้าไปนิดเดียว! เกล็ดหิมะละลายไปแล้ว\n"
            f"(ลิงก์นี้ถือว่าใช้ไปแล้วนะ ต้องไปโรลเพลย์ใหม่มาแก้ตัว!)"
        )
        # บันทึกลิงก์ว่าใช้ไปแล้ว แม้จะแพ้ (เพื่อกันเอาลิงก์เดิมมาสแปม)
        links_list.append(link)
        update_snow_progress(user_id, count, False, links_list)

# 3. เช็คสถานะ (Admin)
@snow_group.command(name="check", description="[Admin] เช็คยอดเกล็ดหิมะ")
async def snow_check(interaction: discord.Interaction):
    if interaction.user.id != ADMIN_ID:
        await interaction.response.send_message("เฉพาะ Admin ครับ", ephemeral=True)
        return
    
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, count, completed FROM snowflakes")
        players = cursor.fetchall()
        
    if not players:
        await interaction.response.send_message("ยังไม่มีใครเล่นครับ", ephemeral=True)
        return

    report = "**📊 รายงานภารกิจ Snowflake**\n"
    for row in players:
        uid, cnt, comp = row
        status = "✅ ครบแล้ว" if comp else f"❄️ {cnt}/5"
        report += f"• <@{uid}> : {status}\n"
        
    await interaction.response.send_message(report, ephemeral=True)

# --- เพิ่ม Group เข้า Tree (บรรทัดนี้สำคัญมาก ห้ามลืม!) ---
client.tree.add_command(snow_group)

# Run Bot
client.run(TOKEN)
