import os
import re
import csv
from typing import List
from playwright.sync_api import sync_playwright


class PropertyDataScraper:
    def __init__(self, output_file: str = "inmuebles.csv", max_properties: int = 200):
        self.output_file = output_file
        self.max_properties = max_properties
        self.property_links = set()
        self.properties_data = []

    def run(self, base_url: str, validation_url: str):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()

            current_page = 1
            while len(self.properties_data) < self.max_properties:
                url = f"{base_url}?pag={current_page}"
                print(f"Procesando página {current_page}: {url}")
                page.goto(url, wait_until="domcontentloaded", timeout=60000)

                # Extraer links de propiedades
                self._extract_property_links(page, validation_url)

                # Procesar cada propiedad
                for link in list(self.property_links):
                    if len(self.properties_data) >= self.max_properties:
                        break
                    self._extract_property_data(context, link)

                # Paginación: salir si no hay más páginas
                next_page_links = page.locator("#paginador a").all()
                if not any(link.text_content() == ">" for link in next_page_links):
                    break

                current_page += 1

            browser.close()
            self._save_to_csv()
            print(f"\nScraping finalizado. Se guardaron {len(self.properties_data)} propiedades en '{self.output_file}'")

    def _extract_property_links(self, page, validation_url: str):
        links = page.locator("a").all()
        for link in links:
            href = link.get_attribute("href")
            if href and href.startswith(validation_url) and re.search(r"-\d{8}$", href):
                full_url = href if href.startswith("http") else f"https://www.gallito.com.uy{href}"
                self.property_links.add(full_url)

    def _extract_property_data(self, context, link: str):
        try:
            page = context.new_page()
            print(f"Extrayendo: {link}")
            page.goto(link, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_selector("div.wrapperDatos", timeout=15000)

            title = page.locator("h1.titulo").text_content()
            address = page.locator("h2.direccion").text_content()
            price = page.locator("span.precio").text_content()
            wrapper_items = page.locator("div.wrapperDatos p").all_text_contents()

            # Inicializar campos
            operation = ""
            neighborhood = ""
            bedrooms = ""
            bathrooms = ""
            mts = ""

            for item in wrapper_items:
                item_lower = item.lower()
                if "venta" in item_lower or "alquiler" in item_lower:
                    operation = item
                elif "mts" in item_lower:
                    mts = item
                elif "baño" in item_lower:
                    bathrooms = item
                elif "dormitorio" in item_lower:
                    bedrooms = item
                else:
                    neighborhood = item

            self.properties_data.append({
                "titulo": title.strip() if title else "",
                "direccion": address.strip() if address else "",
                "precio": price.strip() if price else "",
                "operacion": operation.strip(),
                "barrio": neighborhood.strip(),
                "dormitorios": bedrooms.strip(),
                "banos": bathrooms.strip(),
                "metros": mts.strip(),
                "url": link
            })

            page.close()
        except Exception as e:
            print(f"Error al procesar {link}: {e}")

    def _save_to_csv(self):
        fieldnames = ["titulo", "direccion", "precio", "operacion", "barrio", "dormitorios", "banos", "metros", "url"]
        os.makedirs(os.path.dirname(self.output_file), exist_ok=True)
        with open(self.output_file, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.properties_data)


if __name__ == "__main__":
    scraper = PropertyDataScraper(output_file="data/inmuebles.csv", max_properties=2000)
    scraper.run(
        base_url="https://www.gallito.com.uy/inmuebles/venta/montevideo",
        validation_url="https://www.gallito.com.uy"
    )
