from dataclasses import dataclass


@dataclass(frozen=True)
class Product:
    id: str
    section: str
    category: str
    name: str
    subtitle: str
    description: str
    base_rate: float
    minimum_price: float
    directions: tuple[str, ...]
    glass_colors: tuple[str, ...]
    frame_colors: tuple[str, ...]
    accent: str
    hero_image: str = ""
    detail_images: tuple[str, ...] = ()
    active: bool = True
    updated_at: str = ""
    color_options: tuple[str, ...] = ()
    color_images: tuple[tuple[str, str], ...] = ()
    color_information: str = ""
    stock_information: str = ""
