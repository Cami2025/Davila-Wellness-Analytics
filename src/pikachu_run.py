"""
Animación simple de Pikachu corriendo en la terminal.

Ejecuta este archivo directamente para ver la animación:
    python src/pikachu_run.py

La animación usa cuadros ASCII que se repiten en bucle. Puedes cambiar la
velocidad ajustando la constante FRAME_DELAY.
"""
import os
import sys
import time
from itertools import cycle

FRAME_DELAY = 0.15  # segundos entre cuadros


PIKACHU_FRAMES = [
    r"""
    (\__/)
    (o^.^)    🏃
   z(_(")(")
""",
    r"""
    (\__/)
    (^-.^o)   🏃
   z(_(")(")
""",
    r"""
    (\__/)
    (o^.^)    🏃
    (_(")(")z
""",
    r"""
    (\__/)
    (^-.^o)   🏃
    (_(")(")z
""",
]


def clear_screen() -> None:
    """Limpia la pantalla de forma compatible con Windows y Unix."""
    os.system("cls" if os.name == "nt" else "clear")


def animate_pikachu(cycles: int | None = None) -> None:
    """Muestra un Pikachu corriendo.

    Args:
        cycles: cantidad de veces que se repiten los cuadros. Si es None,
            la animación corre indefinidamente.
    """
    frame_iter = cycle(PIKACHU_FRAMES)
    count = 0

    try:
        for frame in frame_iter:
            clear_screen()
            print(frame)
            time.sleep(FRAME_DELAY)

            if cycles is not None:
                count += 1
                if count >= cycles:
                    break
    except KeyboardInterrupt:
        pass


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada de consola."""
    argv = argv or sys.argv[1:]

    # Permitir un número opcional de ciclos: python pikachu_run.py 40
    limit = None
    if argv:
        try:
            limit = int(argv[0])
        except ValueError:
            print("Uso: python src/pikachu_run.py [ciclos]")
            return 1

    animate_pikachu(limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
