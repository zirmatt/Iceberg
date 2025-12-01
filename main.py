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
        
        # 1. ตาราง Iceberg
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS players (
                user_id INTEGER PRIMARY KEY,
                attempts INTEGER DEFAULT 0,
                target_attempts INTEGER DEFAULT 10,
                completed INTEGER DEFAULT 0,
                links TEXT DEFAULT '[]'
            )
        ''')
        
        # 2. ตาราง Snowflakes
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS snowflakes (
                user_id INTEGER PRIMARY KEY,
                count INTEGER DEFAULT 0,
                completed INTEGER DEFAULT 0,
                links TEXT DEFAULT '[]'
            )
        ''')

        # 3. ตาราง Vault
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vaults (
                team_id TEXT PRIMARY KEY,
                user1_id INTEGER,
                user2_id INTEGER,
                role_warmer INTEGER,
                role_turner INTEGER,
                attempts INTEGER DEFAULT 0,
                target_attempts INTEGER DEFAULT 10,
                completed INTEGER DEFAULT 0,
                links TEXT DEFAULT '[]',
                round_link_u1 TEXT,
                round_link_u2 TEXT
            )
        ''')
        conn.commit()

# --- ICEBERG DB FUNCTIONS ---
def get_player(user_id):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT attempts, target_attempts, completed, links FROM players WHERE user_id = ?", (user_id,))
        return cursor.fetchone()

def create_player(user_id, link, target):
    with sqlite3.connect(DB_NAME) as conn:
        links_json = json.dumps([link])
        conn.execute("INSERT INTO players (user_id, attempts, target_attempts, completed, links) VALUES (?, 0, ?, 0, ?)", 
                     (user_id, target, links_json))

def update_player_progress(user_id, attempts, completed, links_list):
    with sqlite3.connect(DB_NAME) as conn:
        links_json = json.dumps(links_list)
        conn.execute("UPDATE players SET attempts = ?, completed = ?, links = ? WHERE user_id = ?", 
                     (attempts, 1 if completed else 0, links_json, user_id))

def delete_player(user_id):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("DELETE FROM players WHERE user_id = ?", (user_id,))

def get_all_players():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, attempts, target_attempts, completed FROM players")
        return cursor.fetchall()

# --- SNOWFLAKE DB FUNCTIONS ---
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

def delete_snow_player(user_id):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("DELETE FROM snowflakes WHERE user_id = ?", (user_id,))

# --- VAULT DB FUNCTIONS ---
def get_vault_team(user_id):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT team_id, user1_id, user2_id, role_warmer, role_turner, 
                   attempts, target_attempts, completed, links, 
                   round_link_u1, round_link_u2
            FROM vaults WHERE user1_id = ? OR user2_id = ?
        """, (user_id, user_id))
        return cursor.fetchone()

def create_vault_team(user1_id, user2_id, target):
    team_id = f"{user1_id}_{user2_id}"
    roles_config = random.choice([0, 1]) 
    warmer_id = user1_id if roles_config == 0 else user2_id
    turner_id = user2_id if roles_config == 0 else user1_id
    
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("""
            INSERT INTO vaults (team_id, user1_id, user2_id, role_warmer, role_turner, 
                                attempts, target_attempts, completed, links, round_link_u1, round_link_u2) 
            VALUES (?, ?, ?, ?, ?, 0, ?, 0, '[]', NULL, NULL)
        """, (team_id, user1_id, user2_id, warmer_id, turner_id, target))
    return warmer_id, turner_id

def update_vault_round_link(team_id, is_user1, link):
    with sqlite3.connect(DB_NAME) as conn:
        if is_user1:
            conn.execute("UPDATE vaults SET round_link_u1 = ? WHERE team_id = ?", (link, team_id))
        else:
            conn.execute("UPDATE vaults SET round_link_u2 = ? WHERE team_id = ?", (link, team_id))

def complete_vault_round(team_id, attempts, completed, links_list):
    with sqlite3.connect(DB_NAME) as conn:
        links_json = json.dumps(links_list)
        conn.execute("""
            UPDATE vaults SET attempts = ?, completed = ?, links = ?, 
                              round_link_u1 = NULL, round_link_u2 = NULL 
            WHERE team_id = ?
        """, (attempts, 1 if completed else 0, links_json, team_id))

def delete_vault_team(team_id):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("DELETE FROM vaults WHERE team_id = ?", (team_id,))

def get_all_vaults():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user1_id, user2_id, attempts, target_attempts, completed FROM vaults")
        return cursor.fetchall()


# --- BOT SETUP ---
class MyClient(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)

    async def on_ready(self):
        init_db()
        await self.tree.sync()
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="พวกมานุด"))
        print(f'Logged in as {self.user} (Iceberg Systems Online!)')

client = MyClient()

# ==================================================================
# 🧊 GROUP 1: ICEBERG (ทุบน้ำแข็ง - Solo)
# ==================================================================
iceberg_group = app_commands.Group(name="iceberg", description="มาทุบน้ำแข็งกับข้า! Iceberg")

@iceberg_group.command(name="start", description="ส่งลิงก์รับภารกิจเพื่อเริ่มทุบน้ำแข็ง")
@app_commands.describe(link="วางลิงก์โพสต์ที่โรลเพลย์รับภารกิจ")
async def start(interaction: discord.Interaction, link: str):
    user_id = interaction.user.id
    player = get_player(user_id)
    
    if player:
        await interaction.response.send_message("⛄ **ไอซ์เบิร์ก:** โอ๊ยย! เอ็งลงชื่อไปแล้วนี่หว่า ไปใช้คำสั่ง `/iceberg submit` เพื่อทุบน้ำแข็งนู่น!", ephemeral=True)
        return
    if not link.startswith(TARGET_URL):
        await interaction.response.send_message(f"⛄ **ไอซ์เบิร์ก:** ลิงก์อะไรเนี่ย? ข้าไม่รับ! เอาลิงก์ `{TARGET_URL}` มา", ephemeral=True)
        return

    # ICEBERG TARGET: 4-19 ครั้ง
    target_attempts = random.randint(4, 19)
    create_player(user_id, link, target_attempts)
    
    embed = discord.Embed(
        title="⛄ ไอซ์เบิร์ก: \"หึ! คิดว่าจะแน่สักแค่ไหนเชียว!\"",
        description=(
            f"เห็นก้อนน้ำแข็งตรงหน้าไหม? ไม่มีอะไรยากเลย แค่หาทางทำลายมัน\n"
            "บอกไว้ก่อนว่าก้อนนี้แข็งเป็นพิเศษ พนันเลยว่าเจ้าต้องทุบจนมือหักแน่!\n\n"
            "**วิธีเล่น:**\n"
            "1. โรลเพลย์หาทางทุบน้ำแข็งยังไงก็ได้ (หมายเหตุ: ทุบน้ำแข็ง [จำนวน])\n"
            "2. ส่งลิงก์ด้วย `/iceberg submit` พร้อมแนบลิงก์โรลเพลย์มา\n"
            "3. ทุบไปเรื่อย ๆ จนกว่ามันจะแตก (จะทุบได้เร็วมากแค่ไหนขึ้นอยู่กับแรงของเจ้า)"
        ),
        color=0xa5f3fc 
    )
    embed.set_thumbnail(url="https://media.tenor.com/t2akJIhYv6QAAAAM/skibidi-snowmen.gif")
    await interaction.response.send_message(embed=embed)

@iceberg_group.command(name="submit", description="ส่งลิงก์โรลเพลย์เพื่อทุบน้ำแข็ง")
@app_commands.describe(link="วางลิงก์โพสต์ที่นี่")
async def submit(interaction: discord.Interaction, link: str):
    user_id = interaction.user.id
    player = get_player(user_id)
    
    if not player:
        await interaction.response.send_message("⛄ **ไอซ์เบิร์ก:** ยังไม่ได้เริ่มภารกิจเลย! พิมพ์ `/iceberg start` ก่อนเส้!", ephemeral=True)
        return
    
    attempts, target, completed, links_str = player
    links_list = json.loads(links_str)
    
    if completed:
        await interaction.response.send_message("⛄ **ไอซ์เบิร์ก:** มันแตกไปแล้ว! จะมาทุบซ้ำทำไม?", ephemeral=True)
        return
    if not link.startswith(TARGET_URL):
        await interaction.response.send_message(f"⛄ **ไอซ์เบิร์ก:** ลิงก์ผิด! ไปเอาลิงก์โพสต์ที่ถูกมา", ephemeral=True)
        return
    if link in links_list:
        await interaction.response.send_message("⛄ **ไอซ์เบิร์ก:** ลิงก์นี้ใช้ไปแล้ว! อย่าลักไก่ ไปโรลมาใหม่!", ephemeral=True)
        return

    # Process
    links_list.append(link)
    new_attempts = attempts + 1
    
    # Check Success
    is_success = new_attempts >= target

    if is_success: 
        update_player_progress(user_id, new_attempts, True, links_list)
        
        success_msg = (
            f"🎉 **อะๆ เก่งมาก แปะแปะแปะ**\n"
            f"ทุบไปตั้ง {new_attempts} ครั้ง... ยอมใจความถึกจริงๆ\n"
            f"อย่าลืมไปทำภารกิจหาชิ้นส่วนอื่นให้ครบด้วยล่ะ บ๊ายบาย!\n\n"
            f"📢 <@{ADMIN_ID}> เจ้านายมาดูผลงานหน่อยครับ!"
        )
        embed = discord.Embed(
            title="🧊 เพล้งงงง! น้ำแข็งแตกกระจาย!",
            description=success_msg,
            color=0x4ade80
        )
        embed.set_image(url="https://iili.io/fxKE729.png")
        await interaction.response.send_message(content=f"<@{user_id}> <@{ADMIN_ID}>", embed=embed)

    else:
        update_player_progress(user_id, new_attempts, False, links_list)
        
        taunts = [
            "🥱 **ไอซ์เบิร์ก:** ยัง... ยังไม่แตกอีก แรงมีแค่นี้เหรอ?",
            "🤣 **ไอซ์เบิร์ก:** สะกิดแรงกว่านี้หน่อยสิ!",
            "🧊 **ไอซ์เบิร์ก:** ร้าวไปนิดนึง... นิดเดียวจริง ๆ",
            "🥶 **ไอซ์เบิร์ก:** หนาวล่ะสิ มือสั่นทุบไม่โดนหรือไง?",
            "🔨 **ไอซ์เบิร์ก:** เสียงดังฟังชัด แต่ดาเมจเป็นศูนย์!",
            f"👀 **ไอซ์เบิร์ก:** (ทุบไป {new_attempts} ทีแล้วนะ ยังไม่เหนื่อยอีกเหรอ?)"
        ]
        chosen_taunt = random.choice(taunts)

        embed = discord.Embed(
            title=f"💥 โป๊ก! (ครั้งที่ {new_attempts})",
            description=chosen_taunt + "\n\n*อย่าเพิ่งท้อนะไอ้หนู ออกแรงกว่านี้อีกเส้!*",
            color=0xef4444
        )
        await interaction.response.send_message(embed=embed)

@iceberg_group.command(name="check", description="[Admin] เช็คสถานะ Iceberg")
async def check_status(interaction: discord.Interaction):
    if interaction.user.id != ADMIN_ID:
        await interaction.response.send_message("⛄ **ไอซ์เบิร์ก:** ยุ่งน่า! เฉพาะเจ้านายแมทธิวเท่านั้น!", ephemeral=True)
        return

    players = get_all_players()
    if not players:
        await interaction.response.send_message("📂 เงียบกริบ... ยังไม่มีใครเล่นเลยครับเจ้านาย", ephemeral=True)
        return

    report = "**📊 รายงาน Iceberg (Target 4-19)**\n"
    count_success = 0
    for row in players:
        uid, att, target, comp = row
        status = "✅ แตกแล้ว" if comp else f"🔨 {att}/{target}"
        report += f"• <@{uid}> : {status}\n"
        if comp: count_success += 1
    
    report += f"\n👥 ทั้งหมด: {len(players)} | 🎉 สำเร็จ: {count_success}"
    await interaction.response.send_message(report, ephemeral=True)

@iceberg_group.command(name="reset", description="[Admin] รีเซ็ต Iceberg ผู้เล่น")
@app_commands.describe(member="เลือกคนที่จะรีเซ็ต")
async def reset_user(interaction: discord.Interaction, member: discord.Member):
    if interaction.user.id != ADMIN_ID:
        await interaction.response.send_message("❌ เฉพาะ Admin", ephemeral=True)
        return
    
    player = get_player(member.id)
    if player:
        delete_player(member.id)
        await interaction.response.send_message(f"♻️ **Iceberg:** ลบข้อมูล {member.mention} แล้ว ให้เริ่มใหม่ได้เลย", ephemeral=True)
    else:
        await interaction.response.send_message(f"⚠️ หาไม่เจอ", ephemeral=True)

# ==================================================================
# ❄️ GROUP 2: SNOWFLAKE SNATCHER (เกมคว้าเกล็ดหิมะ)
# ==================================================================
snow_group = app_commands.Group(name="snowflake", description="ภารกิจคว้าเกล็ดหิมะ (ต้องเก็บให้ครบ 5 ชิ้น)")

class SnatchView(discord.ui.View):
    def __init__(self, user_id, time_limit):
        super().__init__(timeout=time_limit)
        self.user_id = user_id
        self.clicked = False

    @discord.ui.button(label="❄️ คว้าเลย!", style=discord.ButtonStyle.success)
    async def grab_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("ยุ่งน่า! ไม่ใช่ของเอ็ง อย่ามาแย่ง!", ephemeral=True)
            return
        
        self.clicked = True
        button.disabled = True
        button.label = "คว้าทัน!"
        await interaction.response.edit_message(view=self)
        self.stop()

@snow_group.command(name="start", description="รับภารกิจสะสมเกล็ดหิมะ")
@app_commands.describe(link="วางลิงก์โพสต์แรกเพื่อเริ่มงาน")
async def snow_start(interaction: discord.Interaction, link: str):
    user_id = interaction.user.id
    player = get_snow_player(user_id)

    if player:
        await interaction.response.send_message("❄️ **แมทธิว:** คุณรับภารกิจนี้ไปแล้วครับ เริ่มสะสมด้วยคำสั่ง `/snowflake snatch` ได้เลย", ephemeral=True)
        return
    if not link.startswith(TARGET_URL):
        await interaction.response.send_message(f"❌ ลิงก์ไม่ถูกต้องครับ", ephemeral=True)
        return

    create_snow_player(user_id, link)
    
    embed = discord.Embed(
        title="❄️ พายุหิมะโหมกระหน่ำ?",
        description=(
            f"สวัสดีครับ ผมต้องการเกล็ดหิมะที่สมบูรณ์ทั้งหมด 5 ชิ้น\n"
            "มันจะตกลงมาเร็วมาก คุณต้องตาไวหน่อยนะ\n\n"
            "**วิธีเล่น:**\n"
            "1. โรลเพลย์เดินตามหาจุดที่หิมะตกเพื่อเก็บหิมะที่สมบูรณ์แบบ\n"
            "2. มาพิมพ์ `/snowflake snatch`\n พร้อมแนบลิงก์โรลเพลย์"
            "3. รอจังหวะ... พอปุ่มสีเขียวเด้งขึ้นมา ให้รีบกด **'คว้าเลย!'** ให้ทัน\n"
            "4. ยิ่งเก็บเยอะ... เวลาจะยิ่งน้อยลง ระวังให้ดีล่ะ"
        ),
        color=0xffffff
    )
    await interaction.response.send_message(embed=embed)

@snow_group.command(name="snatch", description="ส่งลิงก์แล้วรอกดปุ่มคว้าหิมะ!")
@app_commands.describe(link="วางลิงก์โรลเพลย์ล่าสุด")
async def snow_snatch(interaction: discord.Interaction, link: str):
    user_id = interaction.user.id
    player = get_snow_player(user_id)

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
        await interaction.response.send_message("⚠️ ลิงก์ซ้ำ! ต้องเป็นโรลเพลย์ใหม่นะครับ", ephemeral=True)
        return

    await interaction.response.defer() 

    embed_wait = discord.Embed(title="👀 กำลังเพ่งมองท้องฟ้า...", description="รอก่อนนะ... อย่าเพิ่งกะพริบตา...", color=0x95a5a6)
    original_msg = await interaction.followup.send(embed=embed_wait)

    await asyncio.sleep(random.uniform(2, 5))

    time_limit = 3.0 - (count * 0.5) 
    if time_limit < 0.8: time_limit = 0.8 

    view = SnatchView(user_id, time_limit)
    embed_now = discord.Embed(title="❄️ หิมะร่วงลงมาแล้ว!!", description=f"**กดปุ่มเดี๋ยวนี้!!** (ภายใน {time_limit} วินาที)", color=0x2ecc71)
    await interaction.edit_original_response(embed=embed_now, view=view)

    await view.wait()

    if view.clicked:
        links_list.append(link)
        new_count = count + 1
        is_finished = (new_count >= 5)
        
        update_snow_progress(user_id, new_count, is_finished, links_list)

        if is_finished:
            embed_win = discord.Embed(
                title="💎 รวบรวมเกล็ดหิมะครบแล้ว!",
                description=f"สุดยอด! คุณคว้าเกล็ดหิมะครบ **5/5 ชิ้น** แล้ว!\nยินดีด้วยครับ อย่าลืมไปทำภารกิจหาชิ้นส่วนอื่นให้ครบด้วยล่ะ!",
                color=0x87a5da
            )
            embed_win.set_image(url="https://iili.io/fxKERr7.png")
            await interaction.followup.send(content=f"<@{user_id}> <@{ADMIN_ID}>", embed=embed_win)
        else:
            await interaction.followup.send(f"✅ **คว้าทัน!** (สะสม: {new_count}/5)\nเก่งมาก! ไปโรลเพลย์หาชิ้นต่อไปมา!")
    else:
        links_list.append(link)
        update_snow_progress(user_id, count, False, links_list)
        await interaction.followup.send(f"💨 **ว้า... พลาด!**\nเกล็ดหิมะละลายไปแล้ว (เวลา {time_limit} วิ)\n(ลิงก์นี้ถือว่าใช้ไปแล้วนะ ต้องไปโรลใหม่!)")

@snow_group.command(name="check", description="[Admin] เช็คยอดเกล็ดหิมะ")
async def snow_check(interaction: discord.Interaction):
    if interaction.user.id != ADMIN_ID:
        await interaction.response.send_message("เฉพาะคุณแมทธิวครับ", ephemeral=True)
        return
    
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, count, completed FROM snowflakes")
        players = cursor.fetchall()
        
    if not players:
        await interaction.response.send_message("ยังไม่มีใครเล่นเลยครับ", ephemeral=True)
        return

    report = "**📊 รายงาน Snowflake**\n"
    for row in players:
        uid, cnt, comp = row
        status = "✅ ครบ" if comp else f"❄️ {cnt}/5"
        report += f"• <@{uid}> : {status}\n"
    await interaction.response.send_message(report, ephemeral=True)

@snow_group.command(name="reset", description="[Admin] รีเซ็ต Snowflake ผู้เล่น")
@app_commands.describe(member="เลือกคนที่จะรีเซ็ต")
async def snow_reset(interaction: discord.Interaction, member: discord.Member):
    if interaction.user.id != ADMIN_ID:
        await interaction.response.send_message("❌ เฉพาะ Admin", ephemeral=True)
        return
    
    player = get_snow_player(member.id)
    if player:
        delete_snow_player(member.id)
        await interaction.response.send_message(f"♻️ **Snowflake:** รีเซ็ตข้อมูล {member.mention} เรียบร้อย", ephemeral=True)
    else:
        await interaction.response.send_message(f"⚠️ ไม่พบข้อมูล", ephemeral=True)


# ==================================================================
# 🗝️ GROUP 3: VAULT (ภารกิจคู่หู - ทนความหนาว 4-19 ครั้ง)
# ==================================================================
vault_group = app_commands.Group(name="vault", description="ภารกิจคู่หู: เปิดตู้นิรภัยน้ำแข็ง")

@vault_group.command(name="create", description="จับคู่สร้างทีมเพื่อเริ่มภารกิจ")
@app_commands.describe(partner="แท็กคู่หูของคุณ")
async def vault_create(interaction: discord.Interaction, partner: discord.Member):
    user1 = interaction.user
    user2 = partner

    if user1.id == user2.id:
        await interaction.response.send_message("❌ จับคู่กับตัวเองไม่ได้ครับ! ต้องหาเพื่อน", ephemeral=True)
        return
    if user2.bot:
        await interaction.response.send_message("❌ จับคู่กับบอทไม่ได้ครับ", ephemeral=True)
        return

    # เช็คว่าใครคนใดคนหนึ่งมีทีมอยู่แล้วรึเปล่า
    team1 = get_vault_team(user1.id)
    team2 = get_vault_team(user2.id)

    if team1 or team2:
        await interaction.response.send_message("⚠️ คุณหรือคู่หูของคุณมีทีมอยู่แล้ว! ต้อง `/vault reset` ของเก่าก่อน", ephemeral=True)
        return

    # VAULT TARGET: 4-19 ครั้ง
    target_attempts = random.randint(4, 19)
    warmer_id, turner_id = create_vault_team(user1.id, user2.id, target_attempts)
    
    # กำหนด Role text
    role_msg = ""
    if warmer_id == user1.id:
        role_msg = f"🔥 **Warmer (คนละลาย):** {user1.mention}\n🔑 **Turner (คนไข):** {user2.mention}"
    else:
        role_msg = f"🔥 **Warmer (คนละลาย):** {user2.mention}\n🔑 **Turner (คนไข):** {user1.mention}"

    embed = discord.Embed(
        title="❄️ Vault Team Created: ภารกิจทนความหนาว",
        description=(
            f"จับคู่สำเร็จ! ระหว่าง {user1.mention} และ {user2.mention}\n\n"
            f"**บทบาทของคุณ:**\n{role_msg}\n\n"
            "**กติกา:**\n"
            "1. **Warmer:** โรลเพลย์ใช้ไออุ่นร่างกาย/ลมหายใจทำให้รูน้ำแข็งละลาย ห้ามใช้ไฟเด็ดขาด!\n"
            "2. **Turner:** โรลเพลย์ออกแรงบิดกุญแจ\n"
            "3. **ทั้งคู่ต้องโรลเพลย์** แล้วนำลิงก์มาส่งด้วย `/vault submit` (ต้องส่งทั้ง 2 คนถึงจะจบรอบ)\n"
            "4. ระบบจะสุ่มความสำเร็จ... ต้องทำให้ถึง 100% ถึงจะเปิดออก\n"
            "5. ยิ่งใช้เวลานาน... ยิ่งหนาว!!!"
        ),
        color=0x9b59b6 # สีม่วง
    )
    await interaction.response.send_message(content=f"{user1.mention} {user2.mention}", embed=embed)

@vault_group.command(name="submit", description="ส่งลิงก์ภารกิจคู่หู (ต้องส่งทั้ง 2 คน)")
@app_commands.describe(link="วางลิงก์โพสต์ของคุณ")
async def vault_submit(interaction: discord.Interaction, link: str):
    user_id = interaction.user.id
    team_data = get_vault_team(user_id)

    if not team_data:
        await interaction.response.send_message("⚠️ คุณยังไม่มีทีม! ใช้ `/vault create` ก่อน", ephemeral=True)
        return
    
    # Unpack Data
    team_id, u1, u2, r_warm, r_turn, attempts, target, completed, links_str, r_link1, r_link2 = team_data
    links_list = json.loads(links_str)

    if completed:
        await interaction.response.send_message("✅ ทีมนี้เปิดตู้สำเร็จไปแล้วครับ!", ephemeral=True)
        return
    if not link.startswith(TARGET_URL):
        await interaction.response.send_message("❌ ลิงก์ไม่ถูกต้อง", ephemeral=True)
        return
    if link in links_list:
        await interaction.response.send_message("⚠️ ลิงก์นี้เคยใช้ในรอบก่อนๆ แล้ว! ต้องใช้ลิงก์ใหม่", ephemeral=True)
        return

    # Identify User & Check Duplicate
    is_user1 = (user_id == u1)
    
    if (is_user1 and r_link1) or (not is_user1 and r_link2):
        await interaction.response.send_message("⏳ **ใจเย็นครับ!** คุณส่งลิงก์ของรอบนี้ไปแล้ว **รอคู่หูของคุณส่งก่อน** ถึงจะเริ่มรอบใหม่ได้", ephemeral=True)
        return

    update_vault_round_link(team_id, is_user1, link)
    
    if is_user1: r_link1 = link
    else: r_link2 = link

    if r_link1 and r_link2:
        # --- ครบ 2 คนแล้ว! ประมวลผลรอบได้ ---
        links_list.append(r_link1)
        links_list.append(r_link2)
        new_attempts = attempts + 1
        
        is_success = new_attempts >= target
        
        if is_success:
            complete_vault_round(team_id, new_attempts, True, links_list)
            
            success_embed = discord.Embed(
                title="🔓 ตู้นิรภัยเปิดออกแล้ว! (100%)",
                description=(
                    f"หลังจากร่วมมือกันมา {new_attempts} รอบ (รวม {new_attempts*2} โพสต์)\n"
                    f"ความอบอุ่นและความสามัคคีของพวกคุณเอาชนะน้ำแข็งได้!\n\n"
                    f"🎉 ยินดีด้วย: <@{u1}> และ <@{u2}>\n"
                    f"อย่าลืมไปทำภารกิจหาชิ้นส่วนอื่นให้ครบด้วยล่ะ!"
                ),
                color=0x87a5da
            )
            success_embed.set_image(url="https://iili.io/fxKEzX4.png")
            
            await interaction.response.send_message(content=f"<@{u1}> <@{u2}> <@{ADMIN_ID}>", embed=success_embed)
        
        else:
            raw_percent = int((new_attempts / target) * 100)
            display_percent = min(raw_percent + random.randint(-5, 5), 95) 
            if display_percent < 5: display_percent = 5
            
            complete_vault_round(team_id, new_attempts, False, links_list)
            
            # --- PROGRESSIVE COLD DESCRIPTION ---
            # รายการข้อความบรรยายความหนาวตามลำดับรอบ (รอบที่ 1 -> รอบสุดท้าย)
            cold_desc_list = [
                "", # index 0 (ไม่ใช้)
                "*อากาศเริ่มเย็นแบบเปิดแอร์เบอร์ 18... ขนลุกซู่เหมือนโดนผีหลอก*",
                "*ลมหายใจกลายเป็นไอ... นึกว่าตัวเองเป็นมังกรพ่นควันเท่ๆ แต่จริงๆ คือหนาว*",
                "*มือเริ่มเย็นเจี๊ยบเหมือนจับแก้วกาแฟดำนานเกินไป... ใครก็ได้ขอถุงมือที!*",
                "*ลมพัดแรงจนทรงผมเสียทรงหมดแล้ว! น้ำแข็งเริ่มเกาะคิ้วจนดูแก่ขึ้น 10 ปี*",
                "*ฟันเริ่มกระทบกันกึกๆๆ... เป็นจังหวะสามช่าโดยไม่ได้ตั้งใจ*",
                "*นิ้วแข็งจนขยับยาก... จะแคะจมูกยังลำบากเลยตอนนี้*",
                "*น้ำมูกเริ่มไหลย้อยลงมา... หวังว่าจะไม่มีใครเห็นนะ สู๊ดดด!*",
                "*หนาวจนอยากจะขดตัวเป็นก้อนกลมๆ เหมือนแมว... แต่ติดที่ต้องไขกุญแจเนี่ยสิ*",
                "*เริ่มเห็นภาพหลอนว่ากุญแจกลายเป็นไอติมแท่ง... อยากจะเลียชะมัด*",
                "*หน้าตึงไปหมดแล้ว... ยิ้มไม่ได้เลย กลัวหน้าแตก (แตกจริงๆ นะ)*",
                "*ตัวสั่นพั่บๆๆ เป็นเจ้าเข้า... ใครเปิดเพลง EDM แถวนี้รึเปล่า?*",
                "*ปากสั่นจนพูดไม่รู้เรื่องแล้ว... ยะ...ยะ...อยาก...กะ...กะ...กลับ...บะ...บ้าน!*",
                "*น้ำตาไหลออกมาแล้วแข็งเป็นเม็ดไข่มุก... เก็บไปขายได้ไหมเนี่ย?*",
                "*เริ่มรู้สึกว่าการเป็นก้อนน้ำแข็งประดับสวนก็ไม่เลวนะ... ไม่ต้องขยับ สบายดี*",
                "*สติเริ่มลอย... เห็นเพนกวินเดินสวนสนามผ่านหน้าไป... โบกมือทักทายมันดีไหม?*",
                "*(วิกฤต) วิญญาณพยายามจะหลุดออกจากร่าง... แต่ติดที่น้ำแข็งเกาะขาไว้ ไปไม่ได้!*",
                "*(ขั้นสุด) ตอนนี้สภาพเหมือนไก่แช่แข็งในช่องฟรีซ... ใครก็ได้เอาไดร์เป่าผมมาเป่าที!!!*"
            ]
            
            # เลือกว่าจะเอาข้อความไหน (ถ้ารอบเกิน 17 ให้ใช้ข้อความสุดท้าย)
            idx = min(new_attempts, 17)
            situation_text = cold_desc_list[idx]

            fail_embed = discord.Embed(
                title=f"❄️ Status: FROZEN ({display_percent}%)",
                description=(
                    f"**จบรอบที่ {new_attempts}** (ได้รับลิงก์จากทั้งคู่แล้ว)\n"
                    f"น้ำแข็งละลายไปบ้าง... แต่ยังเปิดไม่ออก!\n\n"
                    f"### {situation_text}"
                ),
                color=0x3498db
            )
            await interaction.response.send_message(content=f"<@{u1}> <@{u2}>", embed=fail_embed)

    else:
        partner_id = u2 if is_user1 else u1
        await interaction.response.send_message(
            f"📥 **รับลิงก์แล้ว!** (รอคู่หู <@{partner_id}> มาส่งงาน...)\n"
            f"*เมื่อเพื่อนส่งครบแล้ว ระบบจะประมวลผลทันที*",
            ephemeral=True
        )

@vault_group.command(name="check", description="[Admin] เช็คทีม Vault ทั้งหมด")
async def vault_check(interaction: discord.Interaction):
    if interaction.user.id != ADMIN_ID:
        await interaction.response.send_message("❌ เฉพาะ Admin", ephemeral=True)
        return

    vaults = get_all_vaults()
    if not vaults:
        await interaction.response.send_message("📂 ยังไม่มีทีม Vault", ephemeral=True)
        return

    report = "**📊 รายงาน Vault Teams (Target 4-19)**\n"
    for row in vaults:
        u1, u2, att, target, comp = row
        status = "✅ Unlock" if comp else f"🔒 {att}/{target}"
        report += f"• Team <@{u1}>+<@{u2}> : {status}\n"
    
    await interaction.response.send_message(report, ephemeral=True)

@vault_group.command(name="reset", description="[Admin] ลบทีม Vault")
@app_commands.describe(member="เลือกสมาชิกในทีมที่จะลบ (ใครก็ได้ในคู่)")
async def vault_reset(interaction: discord.Interaction, member: discord.Member):
    if interaction.user.id != ADMIN_ID:
        await interaction.response.send_message("❌ เฉพาะ Admin", ephemeral=True)
        return
    
    team_data = get_vault_team(member.id)
    if team_data:
        team_id = team_data[0] # index 0 is team_id
        delete_vault_team(team_id)
        await interaction.response.send_message(f"♻️ **Vault:** ลบทีมของ {member.mention} เรียบร้อย (คู่หูก็โดนลบด้วย)", ephemeral=True)
    else:
        await interaction.response.send_message(f"⚠️ สมาชิกคนนี้ไม่มีทีม", ephemeral=True)

# Add Groups to Tree (ตรวจสอบแล้ว: ไม่มี Duplicate!)
client.tree.add_command(iceberg_group)
client.tree.add_command(snow_group)
client.tree.add_command(vault_group)

# Run Bot
client.run(TOKEN)
