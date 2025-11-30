import discord
from discord import app_commands
import random
import os

# --- CONFIGURATION ---
TOKEN = os.getenv('DISCORD_TOKEN') 
TARGET_URL = "https://roleplayth.com/showthread.php?tid="
ADMIN_ID = 432415629245415426  # <-- ID ของ Admin ที่คุณระบุมา

player_data = {}

class MyClient(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)

    async def on_ready(self):
        await self.tree.sync()
        print(f'Logged in as {self.user} (Ready!)')

client = MyClient()

# --- COMMAND: เริ่มภารกิจ ---
@client.tree.command(name="start_mission", description="เริ่มภารกิจถอดรหัส Cryptex")
async def start_mission(interaction: discord.Interaction):
    user_id = interaction.user.id
    if user_id in player_data:
        await interaction.response.send_message("⚠️ คุณได้รับภารกิจไปแล้วครับ!", ephemeral=True)
        return
    
    # สร้างข้อมูลผู้เล่น
    player_data[user_id] = {'attempts': 0, 'completed': False, 'links': []}
    
    embed = discord.Embed(
        title="❄️ ภารกิจ: The Frozen Cryptex",
        description="เริ่มภารกิจแล้ว! ใช้คำสั่ง `/submit_post` เพื่อส่งลิงก์โรลเพลย์ของคุณ",
        color=0x38bdf8
    )
    await interaction.response.send_message(embed=embed)

# --- COMMAND: ส่งงาน ---
@client.tree.command(name="submit_post", description="ส่งลิงก์โรลเพลย์")
@app_commands.describe(link="วางลิงก์โพสต์ roleplayth")
async def submit_post(interaction: discord.Interaction, link: str):
    user_id = interaction.user.id
    
    if user_id not in player_data:
        await interaction.response.send_message("❌ พิมพ์ `/start_mission` ก่อนครับ", ephemeral=True)
        return
    if player_data[user_id]['completed']:
        await interaction.response.send_message("🎉 คุณผ่านภารกิจไปแล้วครับ!", ephemeral=True)
        return
    if not link.startswith(TARGET_URL):
        await interaction.response.send_message(f"❌ ลิงก์ต้องขึ้นต้นด้วย `{TARGET_URL}`", ephemeral=True)
        return
    if link in player_data[user_id]['links']:
        await interaction.response.send_message("⚠️ ลิงก์ซ้ำ! ห้ามส่งลิงก์เดิมนะครับ", ephemeral=True)
        return

    # บันทึกข้อมูล
    player_data[user_id]['links'].append(link)
    player_data[user_id]['attempts'] += 1
    attempts = player_data[user_id]['attempts']
    
    # Logic คำนวณผล (Pity System)
    bonus = 10 if attempts > 5 else 0
    chance = random.randint(1, 100) + bonus
    
    if chance > 80: # ปรับความยากง่ายตรงนี้ (80 = ผ่านยาก)
        player_data[user_id]['completed'] = True
        code = f"KEY-{random.randint(1000,9999)}-{user_id}"
        
        embed = discord.Embed(
            title="🔓 CRITICAL SUCCESS! กลไกปลดล็อค!",
            description=f"**ความพยายามครั้งที่: {attempts}**\n\nยินดีด้วย! กลไก Cryptex เปิดออกแล้ว\n🎫 **Code:** `{code}`",
            color=0x4ade80
        )
        await interaction.response.send_message(embed=embed)
    else:
        embed = discord.Embed(
            title="❄️ FAILED... ยังเปิดไม่ออก",
            description=f"**ความพยายามครั้งที่: {attempts}**\n\nน้ำแข็งยังเกาะแน่นอยู่... ลองโรลเพลย์ใหม่อีกครั้งนะ",
            color=0xef4444
        )
        await interaction.response.send_message(embed=embed)

# --- COMMAND: Admin Reset (เพิ่มใหม่) ---
@client.tree.command(name="admin_reset", description="[Admin Only] รีเซ็ตภารกิจของผู้เล่นให้เริ่มใหม่ได้")
@app_commands.describe(member="เลือกผู้เล่นที่ต้องการรีเซ็ต")
async def admin_reset(interaction: discord.Interaction, member: discord.Member):
    # 1. เช็คว่าเป็น Admin หรือไม่
    if interaction.user.id != ADMIN_ID:
        await interaction.response.send_message("❌ คุณไม่มีสิทธิ์ใช้คำสั่งนี้ครับ (เฉพาะ Admin)", ephemeral=True)
        return

    target_id = member.id
    
    # 2. เช็คว่าผู้เล่นคนนี้มีข้อมูลในระบบไหม
    if target_id in player_data:
        # ลบข้อมูลออก เพื่อให้เริ่มใหม่ได้
        del player_data[target_id]
        
        embed = discord.Embed(
            title="🔄 Mission Reset",
            description=f"ล้างข้อมูลภารกิจของ {member.mention} เรียบร้อยแล้ว\nเขาสามารถเริ่ม `/start_mission` ใหม่ได้ทันที",
            color=0xfacc15 # สีเหลือง
        )
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message(f"⚠️ ไม่พบข้อมูลของผู้เล่น {member.mention} ในระบบ", ephemeral=True)

client.run(TOKEN)
