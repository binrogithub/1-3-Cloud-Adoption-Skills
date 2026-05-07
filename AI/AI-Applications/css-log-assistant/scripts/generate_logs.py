import json
import random
import uuid
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from faker import Faker

LATIN_AMERICA_COUNTRIES = {
    "MX": {
        "name": "Mexico",
        "currency": "MXN",
        "cities": [
            "Mexico City", "Guadalajara", "Monterrey", "Puebla",
            "Tijuana", "Cancun", "Merida", "Leon"
        ],
        "amount_range": (80, 500),
        "restaurants": [
            "Taco Palace", "Burrito Express", "Salsa Verde Kitchen",
            "El Mariachi Grill", "Casa Oaxaca", "La Taqueria",
            "Guacamole House", "Nachos & More", "Fajita Factory",
            "Churro Station", "Mole Poblano", "Tortilla Land"
        ],
    },
    "BR": {
        "name": "Brazil",
        "currency": "BRL",
        "cities": [
            "Sao Paulo", "Rio de Janeiro", "Brasilia", "Salvador",
            "Fortaleza", "Belo Horizonte", "Curitiba", "Recife"
        ],
        "amount_range": (30, 200),
        "restaurants": [
            "Acai Bowl Bar", "Feijoada House", "Churrascaria Gaucho",
            "Pao de Queijo Shop", "Tapioca Express", "Coxinha Corner",
            "Brigadeiro Cafe", "Moqueca Kitchen", "Caipirinha Lounge",
            "Pastel Palace", "Vatapa Grill", "Bob's Burger BR"
        ],
    },
    "AR": {
        "name": "Argentina",
        "currency": "ARS",
        "cities": [
            "Buenos Aires", "Cordoba", "Rosario", "Mendoza",
            "La Plata", "Mar del Plata", "Tucuman", "Salta"
        ],
        "amount_range": (500, 5000),
        "restaurants": [
            "Asado Grill", "Empanada Factory", "Milanesa House",
            "Choripan Stand", "Alfajor Cafe", "Dulce de Leche Bar",
            "Parrilla Portena", "Matambre Kitchen", "Locro Lodge",
            "Humita Express", "Provoleta Place", "Fernet Corner"
        ],
    },
    "CO": {
        "name": "Colombia",
        "currency": "COP",
        "cities": [
            "Bogota", "Medellin", "Cali", "Barranquilla",
            "Cartagena", "Bucaramanga", "Pereira", "Manizales"
        ],
        "amount_range": (10000, 80000),
        "restaurants": [
            "Arepa Station", "Bandeja Paisa House", "Ajiaco Kitchen",
            "Empanada Colombiana", "Sancocho Soup", "Lechona Grill",
            "Chicharron Express", "Tamales Tolima", "Agua de Panela Cafe",
            "Buñuelo Bar", "Pandebono Shop", "Cholado Corner"
        ],
    },
    "CL": {
        "name": "Chile",
        "currency": "CLP",
        "cities": [
            "Santiago", "Valparaiso", "Concepcion", "La Serena",
            "Antofagasta", "Temuco", "Rancagua", "Arica"
        ],
        "amount_range": (3000, 25000),
        "restaurants": [
            "Completo Stand", "Empanada Chilena", "Pastel de Choclo",
            "Cazuela Kitchen", "Asado Chileno", "Mote con Huesillo",
            "Curanto Grill", "Pebre Cafe", "Chorrillana House",
            "Sopaipilla Express", "Manjar Bar", "Terremoto Lounge"
        ],
    },
    "PE": {
        "name": "Peru",
        "currency": "PEN",
        "cities": [
            "Lima", "Arequipa", "Cusco", "Trujillo",
            "Chiclayo", "Piura", "Iquitos", "Huancayo"
        ],
        "amount_range": (15, 120),
        "restaurants": [
            "Cevicheria Lima", "Lomo Saltado House", "Aji de Gallina Kitchen",
            "Anticucho Stand", "Rocoto Relleno", "Causa Limeña",
            "Papa Huancaina", "Arroz con Pato", "Tallarin Verde Pasta",
            "Picarones Corner", "Chicha Morada Bar", "Inca Grill"
        ],
    },
    "EC": {
        "name": "Ecuador",
        "currency": "USD",
        "cities": [
            "Quito", "Guayaquil", "Cuenca", "Manta",
            "Loja", "Ambato", "Portoviejo", "Machala"
        ],
        "amount_range": (5, 40),
        "restaurants": [
            "Encebollado House", "Ceviche Ecuatoriano", "Llapingachos Kitchen",
            "Fanesca Soup", "Hornado Grill", "Churrasco Ecuatoriano",
            "Bolon de Verde", "Empanada de Viento", "Humita Ecuatoriana",
            "Colada Morada Bar", "Guatita Corner", "Seco de Chivo"
        ],
    },
    "UY": {
        "name": "Uruguay",
        "currency": "UYU",
        "cities": [
            "Montevideo", "Punta del Este", "Salto", "Paysandu",
            "Rivera", "Maldonado", "Rocha", "Florida"
        ],
        "amount_range": (100, 800),
        "restaurants": [
            "Chivito Club", "Asado Uruguayo", "Milanesa Montevideo",
            "Empanada Uruguaya", "Pascualina Kitchen", "Chajá Dessert",
            "Torta Frita Stand", "Mate Bar", "Dulce de Leche UY",
            "Fainá Grill", "Gnocchi House", "Medialuna Cafe"
        ],
    },
    "PA": {
        "name": "Panama",
        "currency": "USD",
        "cities": [
            "Panama City", "Colon", "David", "Santiago",
            "Chitre", "Bocas del Toro", "La Chorrera", "Penonome"
        ],
        "amount_range": (5, 50),
        "restaurants": [
            "Sancocho Panama", "Ropa Vieja House", "Arroz con Pollo Kitchen",
            "Ceviche Panameno", "Hojaldra Cafe", "Tamales Panamenos",
            "Carimanuela Grill", "Patacones Express", "Chicheme Bar",
            "Raspadura Corner", "Bolondron Stand", "Guacho Panama"
        ],
    },
    "CR": {
        "name": "Costa Rica",
        "currency": "CRC",
        "cities": [
            "San Jose", "Alajuela", "Heredia", "Cartago",
            "Limon", "Puntarenas", "Guanacaste", "Monteverde"
        ],
        "amount_range": (2000, 15000),
        "restaurants": [
            "Gallo Pinto Kitchen", "Casado House", "Olla de Carne Grill",
            "Tamales Ticos", "Sopa Negra Cafe", "Chifrijo Corner",
            "Arroz con Mariscos", "Rondon Express", "Naturiga Bar",
            "Tres Leches Stand", "Plantain Tico", "Soda La Esquina"
        ],
    },
}

ORDER_STATUSES = {
    "delivered": 0.70,
    "preparing": 0.08,
    "in_transit": 0.07,
    "cancelled_by_customer": 0.05,
    "cancelled_by_restaurant": 0.03,
    "payment_failed": 0.03,
    "delivery_timeout": 0.02,
    "pending": 0.02,
}

PAYMENT_METHODS = ["credit_card", "debit_card", "cash", "digital_wallet", "bank_transfer"]
PLATFORMS = ["android", "ios", "web"]

ERROR_CODES = {
    "cancelled_by_customer": [("CANCEL_CUST_001", "Customer cancelled the order")],
    "cancelled_by_restaurant": [
        ("CANCEL_REST_001", "Restaurant unable to fulfill order"),
        ("CANCEL_REST_002", "Item out of stock"),
    ],
    "payment_failed": [
        ("PAY_FAIL_001", "Card declined"),
        ("PAY_FAIL_002", "Insufficient funds"),
        ("PAY_FAIL_003", "Payment gateway timeout"),
    ],
    "delivery_timeout": [
        ("DEL_TIMEOUT_001", "Driver could not be assigned"),
        ("DEL_TIMEOUT_002", "Delivery exceeded maximum time"),
    ],
}


def weighted_choice(choices_dict):
    items = list(choices_dict.keys())
    weights = list(choices_dict.values())
    return random.choices(items, weights=weights, k=1)[0]


def generate_order_log(fake, country_code, country_config, timestamp):
    order_status = weighted_choice(ORDER_STATUSES)
    city = random.choice(country_config["cities"])
    amount_min, amount_max = country_config["amount_range"]
    total_amount = round(random.uniform(amount_min, amount_max), 2)

    log_entry = {
        "timestamp": timestamp.isoformat() + "Z",
        "order_id": f"ORD-{uuid.uuid4().hex[:10].upper()}",
        "country": country_config["name"],
        "country_code": country_code,
        "city": city,
        "restaurant_id": f"REST-{uuid.uuid4().hex[:8].upper()}",
        "restaurant_name": random.choice(country_config["restaurants"]),
        "customer_id": f"CUST-{uuid.uuid4().hex[:8].upper()}",
        "driver_id": f"DRV-{uuid.uuid4().hex[:8].upper()}",
        "order_status": order_status,
        "total_amount": total_amount,
        "currency": country_config["currency"],
        "items_count": random.randint(1, 8),
        "delivery_time_minutes": random.randint(15, 75) if order_status == "delivered" else None,
        "distance_km": round(random.uniform(0.5, 15.0), 1),
        "payment_method": random.choice(PAYMENT_METHODS),
        "platform": random.choice(PLATFORMS),
        "error_code": None,
        "error_message": None,
    }

    if order_status in ERROR_CODES:
        error = random.choice(ERROR_CODES[order_status])
        log_entry["error_code"] = error[0]
        log_entry["error_message"] = error[1]

    return log_entry


def generate_logs(
    start_date="2025-11-01",
    end_date="2026-05-01",
    logs_per_day=10000,
    output_dir="output",
    batch_size=50000,
):
    fake = Faker("en_US")
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    total_days = (end - start).days

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    country_codes = list(LATIN_AMERICA_COUNTRIES.keys())
    total_logs = total_days * logs_per_day
    print(f"Generating {total_logs:,} logs over {total_days} days ({logs_per_day:,}/day)")
    print(f"Countries: {', '.join(country_codes)}")
    print(f"Output directory: {output_path.resolve()}")

    batch_num = 0
    batch_logs = []
    total_generated = 0

    for day_offset in range(total_days):
        current_date = start + timedelta(days=day_offset)
        if day_offset % 30 == 0:
            print(f"  Day {day_offset}/{total_days}: {current_date.strftime('%Y-%m-%d')}")

        for _ in range(logs_per_day):
            hour = random.choices(range(24), weights=[
                1, 1, 1, 1, 1, 2, 3, 5, 7, 8, 9, 10,
                12, 11, 10, 9, 8, 7, 6, 8, 10, 9, 6, 3
            ], k=1)[0]
            minute = random.randint(0, 59)
            second = random.randint(0, 59)
            timestamp = current_date.replace(hour=hour, minute=minute, second=second)

            country_code = random.choice(country_codes)
            country_config = LATIN_AMERICA_COUNTRIES[country_code]

            log_entry = generate_order_log(fake, country_code, country_config, timestamp)
            batch_logs.append(log_entry)
            total_generated += 1

            if len(batch_logs) >= batch_size:
                batch_num += 1
                filename = output_path / f"logs_batch_{batch_num:04d}.json"
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(batch_logs, f, ensure_ascii=False)
                print(f"  Wrote batch {batch_num}: {len(batch_logs):,} logs -> {filename}")
                batch_logs = []

    if batch_logs:
        batch_num += 1
        filename = output_path / f"logs_batch_{batch_num:04d}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(batch_logs, f, ensure_ascii=False)
        print(f"  Wrote batch {batch_num}: {len(batch_logs):,} logs -> {filename}")

    print(f"\nGeneration complete: {total_generated:,} total logs in {batch_num} batch files")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Latin America food delivery logs")
    parser.add_argument("--start-date", default="2025-11-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", default="2026-05-01", help="End date (YYYY-MM-DD)")
    parser.add_argument("--logs-per-day", type=int, default=10000, help="Number of logs per day")
    parser.add_argument("--output-dir", default="output", help="Output directory for batch files")
    parser.add_argument("--batch-size", type=int, default=50000, help="Logs per batch file")
    args = parser.parse_args()

    generate_logs(
        start_date=args.start_date,
        end_date=args.end_date,
        logs_per_day=args.logs_per_day,
        output_dir=args.output_dir,
        batch_size=args.batch_size,
    )
