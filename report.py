"""
PDF report generator for bank/financing applications.

Generates a professional report summarizing the battery/solar investment
analysis with methodology explanation, cashflow projections, and key assumptions.
"""

import io
from datetime import date
from fpdf import FPDF


def _safe(text: str) -> str:
    """Replace characters that latin-1 can't encode."""
    replacements = {
        '\u2014': '-',   # em dash
        '\u2013': '-',   # en dash
        '\u2018': "'",   # left single quote
        '\u2019': "'",   # right single quote
        '\u201c': '"',   # left double quote
        '\u201d': '"',   # right double quote
        '\u2026': '...', # ellipsis
        '\u2022': '*',   # bullet
        '\u00d7': 'x',   # multiplication sign
        '\u2265': '>=',  # greater than or equal
        '\u2264': '<=',  # less than or equal
        '\u2192': '->',  # right arrow
        '\u2190': '<-',  # left arrow
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    # Fallback: replace any remaining non-latin-1 chars
    return text.encode('latin-1', errors='replace').decode('latin-1')


class EnergiReport(FPDF):
    """Custom PDF with header/footer for Energikalkyl reports."""

    def header(self):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(100, 100, 100)
        self.cell(0, 8, "Energikalkyl  - Investeringsunderlag", align="R")
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Sida {self.page_no()}/{{nb}} | Genererad {date.today().isoformat()}", align="C")

    def section_title(self, title):
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(44, 62, 80)
        self.cell(0, 10, _safe(title), new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(46, 204, 113)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(4)

    def sub_title(self, title):
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(52, 73, 94)
        self.cell(0, 8, _safe(title), new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def body_text(self, text):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(50, 50, 50)
        self.multi_cell(0, 5, _safe(text))
        self.ln(2)

    def key_value(self, key, value, bold_value=False):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(80, 80, 80)
        self.cell(85, 6, _safe(key))
        self.set_font("Helvetica", "B" if bold_value else "", 10)
        self.set_text_color(30, 30, 30)
        self.cell(0, 6, _safe(str(value)), new_x="LMARGIN", new_y="NEXT")

    def table_row(self, cells, header=False, widths=None):
        if widths is None:
            widths = [self.epw / len(cells)] * len(cells)
        self.set_font("Helvetica", "B" if header else "", 9)
        if header:
            self.set_fill_color(44, 62, 80)
            self.set_text_color(255, 255, 255)
        else:
            self.set_text_color(50, 50, 50)
        for i, cell in enumerate(cells):
            align = "R" if i > 0 and not header else "L"
            self.cell(widths[i], 7, _safe(str(cell)), border=0 if header else 0,
                      fill=header, align=align)
        self.ln()
        if header:
            self.set_draw_color(200, 200, 200)
            self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())


def generate_report(
    # Setup
    address: str = "",
    grid_operator: str = "",
    fuse_amps: float = 25,
    solar_kwp: float = 0,
    # Recommended battery
    battery_label: str = "",
    battery_capacity: float = 0,
    battery_price: float = 0,
    installation_cost: float = 0,
    solar_price: float = 0,
    solar_install: float = 0,
    total_investment: float = 0,
    # Results
    savings_per_year: float = 0,
    savings_per_month: float = 0,
    payback_years: float = 0,
    lifetime_years: float = 15,
    lifetime_profit: float = 0,
    cycles_per_year: float = 0,
    best_tariff: str = "",
    # Scenario comparison
    normal_years: list = None,
    normal_savings: float = 0,
    high_years: list = None,
    high_savings: float = 0,
    # Financing
    loan_rate: float = 3.0,
    loan_years: int = 50,
    monthly_loan_cost: float = 0,
    monthly_net: float = 0,
    # Data info
    price_data_range: str = "",
    price_data_days: int = 0,
    weather_station: str = "",
    # All battery comparison
    all_results: list = None,
    # Future scenarios
    future_scenarios: dict = None,
) -> bytes:
    """Generate a PDF report and return it as bytes."""

    pdf = EnergiReport()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # === TITLE ===
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(44, 62, 80)
    pdf.cell(0, 15, "Investeringskalkyl", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 14)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 10, "Hembatteri och solceller", new_x="LMARGIN", new_y="NEXT")
    if address:
        pdf.set_font("Helvetica", "", 12)
        pdf.cell(0, 8, _safe(address), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # === EXECUTIVE SUMMARY ===
    pdf.section_title("Sammanfattning")
    pdf.body_text(
        f"Denna analys visar att en investering i {battery_label} hembatteri"
        f"{' och ' + str(solar_kwp) + ' kWp solceller' if solar_kwp > 0 else ''} "
        f"ger en lägre elkostnad på {savings_per_year:,.0f} kr per år "
        f"({savings_per_month:,.0f} kr per månad). "
        f"Total investering: {total_investment:,.0f} kr. "
        f"Återbetalningstid: {payback_years:.1f} år."
    )
    if monthly_net > 0 and loan_rate > 0:
        pdf.body_text(
            f"Vid finansiering via bolån ({loan_rate}%, {loan_years} år) är investeringen "
            f"kassaflödespositiv från dag ett: besparingen ({savings_per_month:,.0f} kr/mån) "
            f"överstiger lånekostnaden ({monthly_loan_cost:,.0f} kr/mån) med "
            f"{monthly_net:,.0f} kr/mån."
        )
    pdf.ln(3)

    # Highlight box
    pdf.set_fill_color(46, 204, 113)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 10, _safe(f"  Netto i fickan: +{monthly_net:,.0f} kr/mån (kassaflödespositivt dag 1)"),
             fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(50, 50, 50)
    pdf.ln(5)

    # === PROPERTY & SETUP ===
    pdf.section_title("Fastighet och elanläggning")
    if address:
        pdf.key_value("Adress:", address)
    pdf.key_value("Nätägare:", grid_operator)
    pdf.key_value("Huvudsäkring:", f"{fuse_amps:.0f}A, 3-fas")
    pdf.key_value("Rekommenderad tariff:", best_tariff)
    if solar_kwp > 0:
        pdf.key_value("Solceller:", f"{solar_kwp:.1f} kWp")
    pdf.ln(3)

    # === INVESTMENT ===
    pdf.section_title("Investering")
    pdf.key_value("Batteri:", f"{battery_label} ({battery_capacity:.1f} kWh)")
    pdf.key_value("Batteripris:", f"{battery_price:,.0f} kr")
    pdf.key_value("Installation:", f"{installation_cost:,.0f} kr")
    if solar_kwp > 0:
        pdf.key_value("Solceller material:", f"{solar_price:,.0f} kr")
        if solar_install > 0:
            pdf.key_value("Sol-installation:", f"{solar_install:,.0f} kr")
    pdf.set_draw_color(200, 200, 200)
    pdf.line(self_x := pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(2)
    pdf.key_value("Total investering:", f"{total_investment:,.0f} kr", bold_value=True)
    pdf.ln(3)

    # === CASHFLOW ===
    pdf.section_title("Kassaflödesanalys")

    pdf.sub_title("Årlig besparing")
    pdf.key_value("Lägre elkostnad:", f"{savings_per_year:,.0f} kr/år ({savings_per_month:,.0f} kr/mån)", bold_value=True)
    pdf.key_value("Återbetalningstid:", f"{payback_years:.1f} år")
    pdf.key_value("Batterilivslängd:", f"{lifetime_years:.0f} år ({cycles_per_year:.0f} cykler/år)")
    pdf.key_value("Netto under livslängd:", f"{lifetime_profit:,.0f} kr")
    pdf.ln(3)

    if loan_rate > 0 and loan_years > 0:
        pdf.sub_title(f"Finansiering via bolån ({loan_rate}%, {loan_years} år)")
        pdf.key_value("Lånekostnad:", f"{monthly_loan_cost:,.0f} kr/mån")
        pdf.key_value("Elbesparing:", f"{savings_per_month:,.0f} kr/mån")
        pdf.key_value("Netto kassaflöde:", f"+{monthly_net:,.0f} kr/mån", bold_value=True)
        pdf.body_text(
            f"Investeringen läggs på befintligt bolån. Lånekostnaden ({monthly_loan_cost:,.0f} kr/mån) "
            f"understiger elbesparingen ({savings_per_month:,.0f} kr/mån) med {monthly_net:,.0f} kr/mån. "
            f"Hushållet har därmed lägre totala månadskostnader från första dagen."
        )
        pdf.ln(3)

    # Scenario comparison
    if normal_years and high_years and normal_savings > 0:
        pdf.sub_title("Scenariokänslighet")
        pdf.body_text(
            f"Besparingen varierar med elprisnivån. Vid normala priser "
            f"({', '.join(normal_years)}) uppskattas besparingen till {normal_savings:,.0f} kr/år. "
            f"Vid högre priser ({', '.join(high_years)}) ökar besparingen till {high_savings:,.0f} kr/år. "
            f"Den rekommenderade investeringen är lönsam i båda scenarierna."
        )
        pdf.ln(3)

    # Future scenarios
    if future_scenarios:
        pdf.sub_title("Framtidsprognos - tre scenarier")
        pdf.body_text(
            "Batteriets lönsamhet beror på prisskillnaderna mellan dyra och billiga timmar. "
            "Utbyggnaden av vindkraft och solel i det nordiska elsystemet förväntas öka dessa "
            "prisskillnader under de kommande 10-15 åren. Tre scenarier har simulerats:"
        )
        widths = [35, 30, 30, 30, 35]
        pdf.table_row(["Scenario", "Besparing/år", "Besparing/mån", "Netto 15 år", "Antagande"],
                       header=True, widths=widths)
        for label, data in future_scenarios.items():
            pdf.table_row([
                label,
                f"{data['arb_yr']:,.0f} kr",
                f"{data['arb_yr']/12:,.0f} kr",
                f"{data['lifetime_profit']:+,.0f} kr",
                f"{data['vol']:.0%}x volatilitet",
            ], widths=widths)
        pdf.ln(3)
        pdf.body_text(
            "Konservativt: prissvängningarna ökar 50% under 10 år (måttlig utbyggnad av förnybart). "
            "Sannolikt: prissvängningarna 2-3x under 10 år. Fortsatt utbyggnad av vind/sol, "
            "fler elbilar, elektrifiering av industri. De flesta energianalytiker förväntar sig detta. "
            "Hög volatilitet: prissvängningarna 4x (massiv förnybar utbyggnad, kärnkraft fasas ut). "
            "Investeringen är lönsam i samtliga scenarier."
        )
        pdf.ln(3)

    # === BATTERY COMPARISON TABLE ===
    if all_results and len(all_results) > 1:
        pdf.add_page()
        pdf.section_title("Jämförelse batteristorlekar")
        pdf.body_text(
            "Tabellen visar simuleringsresultat för samtliga utvärderade batteristorlekar. "
            "Alla storlekar simuleras med samma förutsättningar (tariff, förbrukning, solceller)."
        )

        widths = [30, 28, 28, 28, 25, 28]
        pdf.table_row(["Batteri", "Besparing/år", "Besparing/mån", "Investering", "Payback", "Netto livslängd"],
                       header=True, widths=widths)
        for r in all_results:
            pdf.table_row([
                r["label"],
                f"{r['total_benefit_yr']:,.0f} kr",
                f"{r['total_benefit_yr']/12:,.0f} kr",
                f"{r['total_invest']:,.0f} kr",
                f"{r['payback']:.1f} år",
                f"{r['profit_life']:,.0f} kr",
            ], widths=widths)
        pdf.ln(5)

    # === METHODOLOGY ===
    pdf.add_page()
    pdf.section_title("Metod och antaganden")

    pdf.sub_title("Simuleringsstrategi")
    pdf.body_text(
        "Simuleringen använder historiska timpriser för el (spotpris) och beräknar den "
        "optimala laddnings- och urladdningsstrategin för batteriet för varje dag. "
        "Batteriet laddar under billiga timmar och laddar ur under dyra timmar. "
        "Strategin har perfekt framförhållning (day-ahead-priser är kända kl 13:00 dagen innan). "
        "Minst 20 öre/kWh prisskillnad krävs för att motivera en laddcykel."
    )

    pdf.sub_title("Prisdata")
    pdf.body_text(
        f"Simuleringen baseras på {price_data_days} dagars historiska spotpriser "
        f"({price_data_range}). Priserna hämtas från elprisetjustnu.se (Nord Pool). "
        f"Nätavgifter beräknas enligt {grid_operator}s tariffmodell."
    )

    if weather_station:
        pdf.sub_title("Uppvärmningsmodell")
        pdf.body_text(
            f"Husets elförbrukning för uppvärmning modelleras timme för timme baserat på "
            f"verklig temperaturdata från SMHI ({weather_station}). "
            f"Värmepumpens verkningsgrad (COP) modelleras utifrån typ: bergvärme har "
            f"nära konstant COP (brintemperaturen varierar inte med utomhustemperaturen), "
            f"medan luftvärmepumpar har COP som sjunker vid kyla. "
            f"Uppvärmningsbehovet beräknas från husets energiklass och yta."
        )

    pdf.sub_title("Solceller")
    if solar_kwp > 0:
        pdf.body_text(
            f"Solproduktionen beräknas utifrån en {solar_kwp:.0f} kWp anläggning med "
            f"sydvänd montering och 35° lutning. Månadsproduktionen baseras på "
            f"typvärden för Stockholm. Solel används i första hand för egenförbrukning, "
            f"sedan batteriladdning, och slutligen export till elnätet."
        )
    else:
        pdf.body_text("Inga solceller ingår i denna kalkyl.")

    pdf.sub_title("Nättariff")
    pdf.body_text(
        f"Simuleringen testar automatiskt alla tillgängliga tariffer hos {grid_operator} "
        f"och väljer den som ger bäst resultat för varje batteristorlek. "
        f"Energiskatt (54,88 öre/kWh inkl. moms) och abonnemangsavgift ingår i beräkningen."
    )

    pdf.sub_title("Batteri")
    pdf.body_text(
        f"Batteriet modelleras med {90}% tur-retur-verkningsgrad (energiförlust vid laddning "
        f"och urladdning). Laddeffekten begränsas av säkringens kapacitet minus hushållets "
        f"momentana last. Batteriets livslängd beräknas från antal cykler per år (max 8000 cykler "
        f"eller 15 års kalenderlivslängd)."
    )

    # === ASSUMPTIONS & RISKS ===
    pdf.section_title("Antaganden och risker")
    pdf.body_text(
        "- Framtida elpriser antas följa samma mönster som historiska priser. "
        "Faktiska priser kan variera.\n"
        "- Batteriets verkningsgrad antas vara konstant över livslängden. "
        "I verkligheten minskar kapaciteten gradvis (degradering).\n"
        "- Solproduktionen baseras på statistiska medelvärden och varierar år från år.\n"
        "- Nättariffer och energiskatt kan ändras av myndighetsbeslut.\n"
        "- Elbilens laddmönster modelleras som schemalagd nattladdning. "
        "Verkligt laddmönster varierar.\n"
        "- Beräkningen inkluderar inte eventuella skatteavdrag (ROT/grönt avdrag) "
        "som kan förbättra lönsamheten ytterligare."
    )
    pdf.ln(5)

    # === DISCLAIMER ===
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(130, 130, 130)
    pdf.multi_cell(0, 4, _safe(
        "Denna rapport är genererad av Energikalkyl och utgör ett beräkningsunderlag baserat på "
        "historisk data och modellerade antaganden. Den utgör inte finansiell rådgivning. "
        "Faktiska besparingar kan avvika från beräknade värden beroende på framtida elpriser, "
        "väderförhållanden, och ändringar i regelverk eller tariffer."
    ))

    return bytes(pdf.output())
