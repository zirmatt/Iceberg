import discord
from discord import app_commands
import random
import os # เพิ่มเพื่อดึงค่าจาก Railway

# --- CONFIGURATION ---
# ดึง Token จาก Environment Variable (ห้ามใส่ตรงนี้เดี๋ยวโดนแฮก)
TOKEN = os.getenv('DISCORD_TOKEN') 
TARGET_URL = "https://roleplayth.com/showthread.php?tid="

player_data = {}

class MyClient(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)

    async def on_ready(self):
        await self.tree.sync()
        print(f'Logged in as {self.user} (Ready!)')

client = MyClient()

@client.tree.command(name="start_mission", description="เริ่มภารกิจถอดรหัส Cryptex")
async def start_mission(interaction: discord.Interaction):
    user_id = interaction.user.id
    if user_id in player_data:
        await interaction.response.send_message("⚠️ รับภารกิจไปแล้วครับ!", ephemeral=True)
        return
    player_data[user_id] = {'attempts': 0, 'completed': False, 'links': []}
    embed = discord.Embed(title="❄️ ภารกิจ: The Frozen Cryptex", description="เริ่มภารกิจแล้ว! ใช้คำสั่ง `/submit_post` เพื่อส่งงาน", color=0x38bdf8)
    await interaction.response.send_message(embed=embed)

@client.tree.command(name="submit_post", description="ส่งลิงก์โรลเพลย์")
@app_commands.describe(link="วางลิงก์โพสต์ roleplayth")
async def submit_post(interaction: discord.Interaction, link: str):
    user_id = interaction.user.id

    if user_id not in player_data:
        await interaction.response.send_message("❌ พิมพ์ `/start_mission` ก่อนครับ", ephemeral=True)
        return
    if player_data[user_id]['completed']:
        await interaction.response.send_message("🎉 คุณผ่านไปแล้วครับ!", ephemeral=True)
        return
    if not link.startswith(TARGET_URL):
        await interaction.response.send_message(f"❌ ลิงก์ต้องขึ้นต้นด้วย `{TARGET_URL}`", ephemeral=True)
        return
    if link in player_data[user_id]['links']:
        await interaction.response.send_message("⚠️ ลิงก์ซ้ำ! ห้ามลักไก่", ephemeral=True)
        return

    player_data[user_id]['links'].append(link)
    player_data[user_id]['attempts'] += 1
    attempts = player_data[user_id]['attempts']

    # Logic คำนวณ
    bonus = 10 if attempts > 5 else 0
    chance = random.randint(1, 100) + bonus

    if chance > 80: # ปรับความยากง่ายตรงนี้ (80 = ผ่านยากพอสมควร)
        player_data[user_id]['completed'] = True
        code = f"KEY-{random.randint(1000,9999)}-{user_id}"
        embed = discord.Embed(title="🔓 SUCCESS!", description=f"ปลดล็อคสำเร็จ!\nCode: `{code}`", color=0x4ade80)
        await interaction.response.send_message(embed=embed)
    else:
        embed = discord.Embed(title="❄️ FAILED", description=f"ยังไม่ออก... (พยายามครั้งที่ {attempts})", color=0xef4444)
        await interaction.response.send_message(embed=embed)

client.run(TOKEN)
