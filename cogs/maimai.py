import os

import discord
import dotenv
from cryptography.fernet import Fernet
from discord import app_commands
from discord.ext import commands
from otoge import MaiMaiClient
from otoge.maimai import MaiMaiAime, MaiMaiPlayRecord

from services.database import Database

dotenv.load_dotenv()


class MaimaiCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.cipherSuite = Fernet(os.getenv("fernet_key").encode())

    group = app_commands.Group(name="maimai", description="maimai関連のコマンド。")

    @group.command(name="link", description="maimaiのアカウントをリンクします。")
    @app_commands.rename(password="パスワード")
    @app_commands.describe(
        segaid="リンクしたいユーザーのSEGA ID。",
        password="リンクしたいユーザーのパスワード。",
    )
    async def linkCommand(
        self, interaction: discord.Interaction, segaid: str, password: str
    ):
        await interaction.response.defer(ephemeral=True)
        client = MaiMaiClient()
        try:
            aimeList = await client.login(segaid, password)
        except Exception as e:
            embed = discord.Embed(
                title="エラーが発生しました！",
                description=f"{e}",
                colour=discord.Colour.red(),
            )
            await interaction.followup.send(embed=embed)
            raise e

        view = discord.ui.View(timeout=300)
        select = discord.ui.Select(
            custom_id="selectAime",
            placeholder="Aimeを選択",
            options=[
                discord.SelectOption(
                    label=aime.name, value=aime.idx, description=aime.trophy
                )
                for aime in aimeList
            ],
        )

        async def selectCallback(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            await Database.pool.execute(
                """
                    INSERT INTO aime (id, segaid, password, aime)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (id)
                    DO UPDATE SET
                        segaid = EXCLUDED.segaid,
                        password = EXCLUDED.password,
                        aime = excluded.aime
                """,
                interaction.user.id,
                self.cipherSuite.encrypt(segaid.encode()).decode(),
                self.cipherSuite.encrypt(password.encode()).decode(),
                int(interaction.data["values"][0]),
            )
            embed = discord.Embed(
                title="ログインしました。",
                colour=discord.Colour.green(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

        select.callback = selectCallback
        view.add_item(select)

        embed = discord.Embed(
            title="ログインしました。",
            description="今後使用するAimeを選択してください。",
            colour=discord.Colour.blurple(),
        )
        await interaction.followup.send(embed=embed, view=view)

    @group.command(name="profile", description="プロフィールを確認します。")
    async def profileCommand(self, interaction: discord.Interaction):
        await interaction.response.defer()
        row = await Database.pool.fetchrow(
            "SELECT * FROM aime WHERE id = $1", interaction.user.id
        )
        if not row:
            embed = discord.Embed(
                title="エラーが発生しました！",
                description="あなたはまだアカウントをリンクしていません！\n`/maimai link`コマンドを使用してアカウントをリンクしてください！",
                colour=discord.Colour.red(),
            )
            await interaction.followup.send(embed=embed)
            return
        client = MaiMaiClient()
        try:
            aimeList = await client.login(
                self.cipherSuite.decrypt(row["segaid"].encode()).decode(),
                self.cipherSuite.decrypt(row["password"].encode()).decode(),
            )
            aime: MaiMaiAime = aimeList[row["aime"]]
            await aime.select()
        except Exception as e:
            embed = discord.Embed(
                title="エラーが発生しました！",
                description=f"{e}",
                colour=discord.Colour.red(),
            )
            await interaction.followup.send(embed=embed)
            raise e

        embed = (
            discord.Embed(
                title=aime.name,
                description=aime.comment,
                colour=discord.Colour.purple(),
            )
            .set_thumbnail(
                url=f"https://beats-api.nennneko5787.net/icon/{interaction.user.id}/maimai"
            )
            .set_author(name=aime.trophy)
            .set_footer(text="maimai")
        )
        await interaction.followup.send(embed=embed)

    def difficultToColor(self, difficult: str):
        match difficult:
            case "BASIC":
                return discord.Colour.green()
            case "ADVANCED":
                return discord.Colour.yellow()
            case "EXPERT":
                return discord.Colour.pink()
            case "MASTER":
                return discord.Colour.purple()
            case "REMASTER":
                return discord.Colour.dark_purple()

    @group.command(name="record", description="プレイ履歴を確認します。")
    async def recordCommand(self, _interaction: discord.Interaction):
        await _interaction.response.defer()
        row = await Database.pool.fetchrow(
            "SELECT * FROM aime WHERE id = $1", _interaction.user.id
        )
        if not row:
            embed = discord.Embed(
                title="エラーが発生しました！",
                description="あなたはまだアカウントをリンクしていません！\n`/maimai link`コマンドを使用してアカウントをリンクしてください！",
                colour=discord.Colour.red(),
            )
            await _interaction.followup.send(embed=embed)
            return
        client = MaiMaiClient()
        try:
            aimeList = await client.login(
                self.cipherSuite.decrypt(row["segaid"].encode()).decode(),
                self.cipherSuite.decrypt(row["password"].encode()).decode(),
            )
            aime: MaiMaiAime = aimeList[row["aime"]]
            await aime.select()
            records = await aime.record()
        except Exception as e:
            embed = discord.Embed(
                title="エラーが発生しました！",
                description=f"{e}",
                colour=discord.Colour.red(),
            )
            await _interaction.followup.send(embed=embed)
            raise e

        view = discord.ui.View(timeout=None)

        leftButton = discord.ui.Button(
            emoji="⏪", style=discord.ButtonStyle.blurple, custom_id="-1", disabled=True
        )
        infoButton = discord.ui.Button(label=f"1 / {len(records)}", disabled=True)
        rightButton = discord.ui.Button(
            emoji="⏩", style=discord.ButtonStyle.blurple, custom_id="1", disabled=False
        )

        async def panel(interaction: discord.Interaction, edit: bool = True):
            leftButton.disabled = int(leftButton.custom_id) + 1 + 1 <= 1
            rightButton.disabled = int(rightButton.custom_id) >= len(records)

            record: MaiMaiPlayRecord = records[int(leftButton.custom_id) + 1]
            embed = (
                discord.Embed(
                    title=record.name,
                    description=f"`{record.percentage} ({record.scoreRank.replace('PLUS', '+')})` {'**NEW RECORD**' if record.percentageIsNewRecord else ''}\nでらっくスコア: `{record.deluxeScore}` {'**NEW RECORD**' if record.deluxeScoreIsNewRecord else ''}\n-# {'クリア' if record.cleared else '未クリア'} \\| {'フルコンボ' if record.fullcombo else '未フルコンボ'} \\| {'SYNC PLAY' if record.sync else 'NO SYNC PLAY'}",
                    colour=self.difficultToColor(record.difficult),
                    timestamp=record.playedAt,
                )
                .set_author(
                    name=aime.name,
                    icon_url=f"https://beats-api.nennneko5787.net/icon/{interaction.user.id}/maimai",
                )
                .set_thumbnail(
                    url=f"https://beats-api.nennneko5787.net/imageProxy?url={record.jacketUrl}",
                )
                .set_footer(text=record.difficult)
            )
            if edit:
                await interaction.edit_original_response(embed=embed, view=view)
            else:
                await interaction.followup.send(embed=embed, view=view)

        async def left(interaction: discord.Interaction):
            if _interaction.user.id != interaction.user.id:
                embed = discord.Embed(
                    title="他の人は操作できません！", colour=discord.Colour.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            await interaction.response.defer()
            leftButton.custom_id = str(int(leftButton.custom_id) - 1)
            infoButton.label = f"{int(leftButton.custom_id) + 1 + 1} / {len(records)}"
            rightButton.custom_id = str(int(rightButton.custom_id) - 1)

            await panel(interaction)

        async def right(interaction: discord.Interaction):
            if _interaction.user.id != interaction.user.id:
                embed = discord.Embed(
                    title="他の人は操作できません！", colour=discord.Colour.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            await interaction.response.defer()
            leftButton.custom_id = str(int(leftButton.custom_id) + 1)
            infoButton.label = f"{int(leftButton.custom_id) + 1 + 1} / {len(records)}"
            rightButton.custom_id = str(int(rightButton.custom_id) + 1)

            await panel(interaction)

        leftButton.callback = left
        rightButton.callback = right

        view.add_item(leftButton)
        view.add_item(infoButton)
        view.add_item(rightButton)

        await panel(_interaction, False)


async def setup(bot: commands.Bot):
    await bot.add_cog(MaimaiCog(bot))
