from discord.ext import commands
import discord
from discord import app_commands
from otoge import POPNClient
from otoge.popn import POPNPlayRecord
from cryptography.fernet import Fernet
import os
import dotenv
import orjson

from .database import Database

dotenv.load_dotenv()

cipherSuite = Fernet(os.getenv("fernet_key").encode())


class KonamiCodeModal(discord.ui.Modal, title="KONAMI IDログイン"):

    def __init__(self, popn: POPNClient):
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


class CookieModal(discord.ui.Modal, title="クッキーログイン"):

    def __init__(self):
        super().__init__()
        self.cookie = discord.ui.TextInput(
            label="Jam&Fizzのクッキー", style=discord.TextStyle.long
        )
        self.add_item(self.cookie)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        await Database.pool.execute(
            """
                INSERT INTO konami (id, cookies)
                VALUES ($1, $2)
                ON CONFLICT (id)
                DO UPDATE SET
                    cookies = EXCLUDED.cookies
            """,
            interaction.user.id,
            cipherSuite.encrypt(self.cookie.value.encode()).decode(),
        )
        embed = discord.Embed(
            title="ログインしました。",
            colour=discord.Colour.green(),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)


class POPNMusicCog(commands.Cog):
    """The description for Popn goes here."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    group = app_commands.Group(name="popn", description="pop'n music関連のコマンド。")

    @group.command(name="cookiehelp", description="クッキーログインの説明")
    async def cookieHelpCommand(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            '## クッキーログインのやり方\n1. ↓をコピーする\n```javascript\njavascript:(function(){var cookies=document.cookie.split(/\\s*;\\s*/).map(function(pair){var parts=pair.split(/\\s*=\\s*/);return{"name":parts[0],"value":parts.slice(1).join("=")};});var json=JSON.stringify(cookies,null,4);var overlay=document.createElement("div");var textarea=document.createElement("textarea");var closeBtn=document.createElement("button");overlay.style.position="fixed";overlay.style.top="0";overlay.style.left="0";overlay.style.width="100%";overlay.style.height="100%";overlay.style.backgroundColor="rgba(0,0,0,0.8)";overlay.style.zIndex="9999";overlay.style.display="flex";overlay.style.flexDirection="column";overlay.style.alignItems="center";overlay.style.justifyContent="center";textarea.value=json;textarea.style.width="80%";textarea.style.height="50%";textarea.style.marginBottom="10px";textarea.style.fontSize="16px";closeBtn.textContent="閉じる";closeBtn.style.padding="10px 20px";closeBtn.style.fontSize="16px";closeBtn.onclick=function(){document.body.removeChild(overlay);};overlay.appendChild(textarea);overlay.appendChild(closeBtn);document.body.appendChild(overlay);textarea.select();})();\n```\n2. https://p.eagate.573.jp/game/popn/jamfizz/ を開く\n3. さっきの謎の文字列をアドレスバーに打ち込み、アドレスバーの先頭に戻り`javascript:`がなければ`javascript:`を追加する\n4. モーダルが出てくるのでテキストボックスの中身をコピーする\n5. `/popn cookie` コマンドを実行しクッキーの欄にテキストボックスの中身を入力する\nおわり',
            ephemeral=True,
        )

    @group.command(
        name="cookie",
        description="クッキーを用いてpop'n musicのアカウントをリンクします。",
    )
    async def cookieHelpCommand(self, interaction: discord.Interaction):
        await interaction.response.send_modal(CookieModal())

    @group.command(
        name="link",
        description="パスワードを用いてpop'n musicのアカウントをリンクします。現在使用できません。",
    )
    @app_commands.rename(password="パスワード")
    @app_commands.describe(
        konamiid="リンクしたいユーザーのKONAMI ID。",
        password="リンクしたいユーザーのパスワード。",
    )
    async def linkCommand(
        self, interaction: discord.Interaction, konamiid: str, password: str
    ):
        await interaction.response.send_message(
            discord.Embed(
                title="このコマンドは現在使用できません。",
                description="`/popn cookie`コマンドを用いてログインしてください。",
            ),
            ephemeral=True,
        )
        """
        await interaction.response.defer(ephemeral=True)
        client = POPNClient()
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
        """

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
        client = POPNClient(skipKonami=True)
        try:
            print(cipherSuite.decrypt(row["cookies"].encode()).decode())
            await client.loginWithCookie(
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

        print(profile.bannerUrl)
        embed = (
            discord.Embed(
                description=f"NORMALモードプレー数: `{profile.normalModePlayCount}`\nBATTLEモードプレー数: `{profile.battleModePlayCount}`\nLOCALモードプレー数: `{profile.localModePlayCount}`\nEXTRAランプレベル: `{profile.extraLampLevel}`",
                timestamp=profile.lastPlayedAt,
                colour=discord.Colour.purple(),
            )
            .set_author(
                name=profile.name,
                icon_url=f"https://otogepictureproxy.onrender.com/{profile.usedCharacters[0].iconUrl}",
            )
            .add_field(
                name="使用キャラクター",
                value="・".join(
                    [character.name for character in profile.usedCharacters]
                ),
            )
            .set_thumbnail(
                url=f"https://otogepictureproxy.onrender.com/{profile.usedCharacters[0].iconUrl}"
            )
            .set_footer(text="pop'n music ･ 最終プレイ日時")
        )
        await interaction.followup.send(embed=embed)

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
        client = POPNClient(skipKonami=True)
        try:
            await client.loginWithCookie(
                orjson.loads(cipherSuite.decrypt(row["cookies"].encode()).decode())
            )
            profile = await client.fetchProfile()
            records = profile.records
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

            record: POPNPlayRecord = records[int(leftButton.custom_id) + 1]
            embed = discord.Embed(
                title=record.name,
                description=f"EASY: `{record.easyScore}`\nNORMAL: `{record.normalScore}`\nHYPER: `{record.hyperScore}`\nEX: `{record.exScore}`",
                colour=discord.Colour.yellow(),
            ).set_author(name=profile.name, icon_url=profile.bannerUrl)
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
    await bot.add_cog(POPNMusicCog(bot))
