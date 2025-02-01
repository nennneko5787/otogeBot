import os

import discord
import dotenv
import orjson
from cryptography.fernet import Fernet
from discord import app_commands
from discord.ext import commands
from otoge import (
    NostalgiaClient,
    NostalgiaProfile,
    NostalgiaDifficulty,
)
from otoge.nostalgia import NostalgiaPlayRecord

from services.database import Database

dotenv.load_dotenv()

cipherSuite = Fernet(os.getenv("fernet_key").encode())


class KonamiCodeModal(discord.ui.Modal, title="KONAMI IDログイン"):

    def __init__(self, popn: NostalgiaClient):
        super().__init__()
        self.popn = popn
        self.code = discord.ui.TextInput(
            label="KONAMI IDログイン用の確認コード", max_length=6, min_length=6
        )
        self.add_item(self.code)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            await self.popn.enterCode(self.code.value)
        except Exception as e:
            embed = discord.Embed(
                title="エラーが発生しました！",
                description=f"{e}",
                colour=discord.Colour.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            raise e
        await Database.pool.execute(
            """
                INSERT INTO konami (id, cookies)
                VALUES ($1, $2)
                ON CONFLICT (id)
                DO UPDATE SET
                    cookies = EXCLUDED.cookies
            """,
            interaction.user.id,
            cipherSuite.encrypt(
                orjson.dumps(
                    [
                        {"name": key, "value": value}
                        for key, value in self.popn.http.cookies.items()
                    ]
                )
            ).decode(),
        )
        embed = discord.Embed(
            title="ログインしました。",
            colour=discord.Colour.green(),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)


class NostalgiaCog(commands.Cog):
    """The description for Popn goes here."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    group = app_commands.Group(name="nos", description="ノスタルジア関連のコマンド。")

    @group.command(
        name="link",
        description="パスワードを用いてKOMANI IDをリンクします。",
    )
    @app_commands.rename(password="パスワード")
    @app_commands.describe(
        konamiid="リンクしたいユーザーのKONAMI ID。",
        password="リンクしたいユーザーのパスワード。",
    )
    async def linkCommand(
        self, interaction: discord.Interaction, konamiid: str, password: str
    ):
        await interaction.response.defer(ephemeral=True)
        client = NostalgiaClient(proxyForCaptcha="localhost:8118")
        try:
            await client.loginWithID(konamiid, password)
        except Exception as e:
            embed = discord.Embed(
                title="エラーが発生しました！",
                description=f"{e}",
                colour=discord.Colour.red(),
            )
            await interaction.followup.send(embed=embed)
            raise e

        async def openModal(interaction: discord.Interaction):
            await interaction.response.send_modal(KonamiCodeModal(client))

        embed = discord.Embed(
            title="KONAMI IDの確認コードを入力してください",
            description="入力ボタンを押し、メールに届いたKONAMI IDの確認コードを入力してください。",
        )
        view = discord.ui.View()
        button = discord.ui.Button(style=discord.ButtonStyle.blurple, label="入力")
        button.callback = openModal
        view.add_item(button)
        await interaction.followup.send(embed=embed, view=view)

    @group.command(name="profile", description="プロフィールを確認します。")
    async def profileCommand(self, interaction: discord.Interaction):
        await interaction.response.defer()
        row = await Database.pool.fetchrow(
            "SELECT * FROM konami WHERE id = $1", interaction.user.id
        )
        if not row:
            embed = discord.Embed(
                title="エラーが発生しました！",
                description="あなたはまだアカウントをリンクしていません！\n`/maimai link`コマンドを使用してアカウントをリンクしてください！",
                colour=discord.Colour.red(),
            )
            await interaction.followup.send(embed=embed)
            return
        client = NostalgiaClient(skipKonami=True)
        try:
            client.loginWithCookie(
                orjson.loads(cipherSuite.decrypt(row["cookies"].encode()).decode())
            )
            profile = await client.fetchProfile()
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
                title=profile.name,
                description=f"所持NOS: `{profile.nos}`\n所持ブローチ: {profile.brooch.name}\nプレイ回数: `{profile.playCount}`",
                timestamp=profile.lastPlayedAt,
                colour=discord.Colour.from_rgb(255, 255, 255),
            )
            .set_author(
                name=profile.fame,
            )
            .set_footer(text="ノスタルジア ･ 最終プレイ日時")
        )
        await interaction.followup.send(embed=embed)

    def switchColor(self, type: NostalgiaDifficulty):
        match type:
            case NostalgiaDifficulty.NORMAL:
                return discord.Colour.green()
            case NostalgiaDifficulty.HARD:
                return discord.Colour.yellow()
            case NostalgiaDifficulty.EXPERT:
                return discord.Colour.red()
            case _:
                return discord.Colour.purple()

    @group.command(name="record", description="プレイ履歴を確認します。")
    async def recordCommand(self, _interaction: discord.Interaction):
        await _interaction.response.defer()
        row = await Database.pool.fetchrow(
            "SELECT * FROM konami WHERE id = $1", _interaction.user.id
        )
        if not row:
            embed = discord.Embed(
                title="エラーが発生しました！",
                description="あなたはまだアカウントをリンクしていません！\n`/maimai link`コマンドを使用してアカウントをリンクしてください！",
                colour=discord.Colour.red(),
            )
            await _interaction.followup.send(embed=embed)
            return
        client = NostalgiaClient(skipKonami=True)
        try:
            client.loginWithCookie(
                orjson.loads(cipherSuite.decrypt(row["cookies"].encode()).decode())
            )
            profile = await client.fetchProfile()
            records = await client.fetchPlayRecords()
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

            record: NostalgiaPlayRecord = records[int(leftButton.custom_id) + 1]
            embed = (
                discord.Embed(
                    title=f"{record.name} [{record.difficulty.name}]",
                    description=f"score: `{record.score}` (best: `{record.bestScore}`)",
                    colour=self.switchColor(record.difficulty),
                    timestamp=record.playedAt,
                )
                .set_author(
                    name=profile.name,
                )
                .set_footer(text=record.license)
                .set_thumbnail(
                    url=f"https://beats-api.nennneko5787.net/imageProxy?url=https://p.eagate.573.jp/game/nostalgia/op3/img/jacket.html?c={record.musicId}"
                )
            )
            embed2 = discord.Embed(
                description=f"PerfectJust: `{record.judge.perfectJust}`\nJust: `{record.judge.just}`\nGood: `{record.judge.good}`\nNear: `{record.judge.near}`\nMiss: `{record.judge.miss}`\nFast: `{record.judge.fast}` / Slow: `{record.judge.slow}`",
                colour=self.switchColor(record.difficulty),
            ).set_footer(text=f"{record.difficulty.name} {record.level}")

            if edit:
                await interaction.edit_original_response(
                    embeds=[embed, embed2], view=view
                )
            else:
                await interaction.followup.send(embeds=[embed, embed2], view=view)

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
    await bot.add_cog(NostalgiaCog(bot))
