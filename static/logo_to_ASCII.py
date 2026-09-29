from PIL import Image

image = Image.open("logo_emblem.png").convert("L")

width = 100
height = int(width * image.height / image.width * 0.55)

image = image.resize((width, height))

symbols = "!@%^&&^%$#@!!@#$%^&*(*&^%#@"

pixels = list(image.getdata())

lines = []

for y in range(height):
    line = ""

    for x in range(width):
        pixel = pixels[y * width + x]

        if pixel < 65:
            line += " "
        else:
            index = min(
                len(symbols) - 1,
                int((pixel - 65) / 190 * len(symbols))
            )

            line += symbols[index]

    lines.append(line.rstrip())

ascii_logo = "\n".join(lines)

with open("logo_ascii.txt", "w", encoding="utf-8") as file:
    file.write(ascii_logo)

print(ascii_logo)