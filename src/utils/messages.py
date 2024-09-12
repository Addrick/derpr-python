import logging
import re

from discord import HTTPException

from src import utils
from src.global_config import DISCORD_CHAR_LIMIT


def break_and_recombine_string(input_string, substring_length, bumper_string):
    substrings = [input_string[i:i + substring_length] for i in range(0, len(input_string), substring_length)]
    formatted_substrings = [bumper_string + substring + bumper_string for substring in substrings]
    combined_string = ' '.join(formatted_substrings)
    return combined_string


def split_string_by_limit(input_string, char_limit):
    """Splits a string between words for easier to read long messages"""  # TODO: maybe split after a period to only send full sentences?
    words = input_string.split(" ")
    current_line = ""
    result = []

    for word in words:
        # Check if adding the next word would exceed the limit
        if len(current_line) + len(word) + 1 > char_limit-1:
            result.append(current_line.strip())
            current_line = word
        else:
            current_line += " " + word

    # Add the last line if there's any content left
    if current_line:
        result.append(current_line.strip())

    return result


async def send_dev_message(channel, msg: str):
    """Escape discord code formatting instances, seems to require this weird hack with a zero-width space"""
    # msg.replace("```", "\```")
    formatted_msg = re.sub('```', '`\u200B``', msg)
    # Split the response into multiple messages if it exceeds 2000 characters
    chunks = split_string_by_limit(formatted_msg, DISCORD_CHAR_LIMIT)
    for chunk in chunks:
        try:
            await channel.send(f"```{chunk}```")
        except HTTPException as e:
            logging.error(f"An error occurred: {e}")
            pass


async def send_message(channel, msg, char_limit):
    """# Set name to currently speaking persona"""
    # await client.user.edit(username=persona_name) #  This doesn't work as name changes are rate limited to 2/hour

    # Split the response into multiple messages if it exceeds max discord message length
    chunks = split_string_by_limit(msg, char_limit)
    for chunk in chunks:
        await channel.send(f"{chunk}")
