# Created by https://github.com/WardPearce

from typing import List
from aiohttp.client import ClientSession, ClientTimeout
from aiohttp.client_exceptions import ContentTypeError
from aiohttp_socks import ProxyConnector, ProxyConnectionError
from discord import AsyncWebhookAdapter, Webhook, Embed
from json import JSONDecodeError
from colorama import Fore
from os import path
from datetime import datetime

import aiojobs
import colorama
import asyncio
import random

# Configuration


# Insta handles to track.
# Should be formatted like the following.
INSTAGRAMS = [
    {
        "handle": "...",
        "webhook": "..."
    },
    {
        "handle": "...",
        "webhook": "..."
    },
]

# Check delay in seconds.
DELAY = 1.0

# General settings
NAME = "..."
ICON_URL = "..."

# Webhook settings.

# Set as None to disable, remove "" if so.
# e.g. WEBHOOK_CONTENT = None
WEBHOOK_CONTENT = None
WEBHOOK_COLOR = 0xFF00C5

ERROR_WEBHOOK = "..."  # Discord webhook to post errors in.
ERROR_WEBHOOK_COLOR = 0xFF0000

# Proxy settings.

PROXY_TIMEOUT = 120  # How long should we wait for a proxy?
PROXY_FILE = True  # IF a proxy file exists.
# Name of proxy file if above true. Needs to be in the directory of this script.
# Should be sock5 only! seperated with line breaks.
PROXY_FILE = "..."
# Leave blank if PROXY_FILE is true
PROXIES = [
]


# DO NOT EDIT!
# unless if you know what you're doing.

HEADERS = {
    "Host": "www.instagram.com",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11"
}

LAST_MESSAGE = []

PROXY_PATH = path.join(
    path.dirname(path.realpath(__file__)),
    PROXY_FILE
)

colorama.init(True)

DISCORD_SESSION = ClientSession()

if ERROR_WEBHOOK:
    DISCORD_ERROR = Webhook.from_url(
        ERROR_WEBHOOK,
        adapter=AsyncWebhookAdapter(DISCORD_SESSION)
    )
else:
    DISCORD_ERROR = None

if PROXY_FILE:
    with open(PROXY_PATH, "r") as f_:
        for proxy_ in f_.read().strip().split():
            PROXIES.append(f"socks5://{proxy_}")


class ProxySessions:
    def __init__(self, proxies: List[str]) -> None:
        self.sessions: List[ClientSession] = [
            ClientSession(
                connector=ProxyConnector.from_url(proxy_),
                timeout=ClientTimeout(total=DELAY - DELAY / 0.5)
            )
            for proxy_ in proxies
        ]
        self.session_len = len(self.sessions) - 1

    def random_session(self) -> ClientSession:
        return self.sessions[random.randint(0, self.session_len)]


proxy = ProxySessions(PROXIES)


async def send_error(error: str) -> None:
    if DISCORD_ERROR:
        embed = Embed(
            title="An error has occurred!",
            color=ERROR_WEBHOOK_COLOR,
            description=f"**__Error__**\n{error}",
            timestamp=datetime.now()
        )

        await DISCORD_ERROR.send(embed=embed)


class Instagram:
    def __init__(self, handle: str, data: dict, webhook: str) -> None:
        self.data = data["graphql"]["user"]
        self.discord = Webhook.from_url(
            webhook,
            adapter=AsyncWebhookAdapter(DISCORD_SESSION)
        )
        self.handle = handle

    @property
    def fullname(self) -> str:
        return self.data["full_name"]

    @property
    def profile_picture(self) -> str:
        return self.data["profile_pic_url_hd"]

    @property
    def total_photos(self) -> int:
        return int(self.data["edge_owner_to_timeline_media"]["count"])

    @property
    def last_publication_url(self) -> str:
        return self.data[
            "edge_owner_to_timeline_media"
        ]["edges"][0]["node"]["shortcode"]

    @property
    def last_photo_url(self) -> str:
        return self.data[
            "edge_owner_to_timeline_media"
        ]["edges"][0]["node"]["display_url"]

    @property
    def last_thumb_url(self) -> str:
        return self.data[
            "edge_owner_to_timeline_media"
        ]["edges"][0]["node"]["thumbnail_src"]

    @property
    def timestamp(self) -> datetime:
        return datetime.fromtimestamp(
            self.data[
                "edge_owner_to_timeline_media"
            ]["edges"][0]["node"]["taken_at_timestamp"]
        )

    @property
    def description_photo(self) -> str:
        url = self.data[
            "edge_owner_to_timeline_media"
        ]["edges"][0]["node"][
            "edge_media_to_caption"
        ]["edges"]

        if len(url) > 0:
            return url[0]["node"]["text"]
        else:
            return "No caption"

    async def send_webhook(self) -> None:
        embed = Embed(
            title=f"New Instagram post from @{self.handle}",
            color=WEBHOOK_COLOR,
            url=f"https://www.instagram.com/p/{self.last_publication_url}/",
            description=self.description_photo,
            timestamp=datetime.now()
        )

        embed.set_thumbnail(url=self.last_thumb_url)
        embed.set_footer(text=NAME, icon_url=ICON_URL)

        await self.discord.send(
            embed=embed,
            username=self.fullname.capitalize(),
            avatar_url=self.profile_picture
        )

        print(Fore.GREEN + "Webhook sent!")


async def parse_insta(handle: str, webhook: str) -> None:
    try:
        resp = await (proxy.random_session()).get(
            f"https://www.instagram.com/{handle}/feed/?__a=1",
            headers=HEADERS,
            allow_redirects=False
        )
    except ProxyConnectionError:
        print(Fore.RED + "Proxy connection error.")
        await parse_insta(handle, webhook)
    else:
        try:
            data = await resp.json()
        except JSONDecodeError as error:
            print(Fore.RED + "Json decoding failed!")
            await send_error(str(error))
        except ContentTypeError:
            pass
        else:
            insta = Instagram(handle, data, webhook)

            if insta.last_publication_url not in LAST_MESSAGE:
                LAST_MESSAGE.append(insta.last_publication_url)
                print(Fore.GREEN + "New post detected!")
                await insta.send_webhook()
            else:
                print(Fore.YELLOW + "Old post.")


if __name__ == "__main__":
    async def main():
        jobs = await aiojobs.create_scheduler()
        print(Fore.GREEN + "Scheduler created!")

        while True:
            for insta in INSTAGRAMS:
                try:
                    await jobs.spawn(
                        parse_insta(insta["handle"], insta["webhook"])
                    )
                except Exception as error:
                    await send_error(str(error))
                else:
                    print(
                        Fore.GREEN
                        +
                        f"{insta['handle']} being sent to {insta['webhook']}"
                    )

            await asyncio.sleep(DELAY)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
