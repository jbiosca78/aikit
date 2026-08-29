function parseCsv(text) {
    const lines = text.trim().split(/\r?\n/);
    const headers = lines[0].split(",").map((h) => h.trim());
    const rows = [];

    for (let i = 1; i < lines.length; i += 1) {
        const row = [];
        let value = "";
        let inQuotes = false;

        for (let j = 0; j < lines[i].length; j += 1) {
            const ch = lines[i][j];
            if (ch === '"') {
                inQuotes = !inQuotes;
                continue;
            }
            if (ch === "," && !inQuotes) {
                row.push(value.trim());
                value = "";
                continue;
            }
            value += ch;
        }
        row.push(value.trim());

        const obj = {};
        headers.forEach((header, idx) => {
            obj[header] = row[idx] || "";
        });
        rows.push(obj);
    }

    return rows;
}

function splitValues(text) {
    return String(text || "")
        .split("|")
        .map((v) => v.trim())
        .filter(Boolean);
}

function toNumber(value) {
    const n = Number(value);
    return Number.isFinite(n) ? n : 0;
}

function stockBadge(item) {
    const stock = toNumber(item.stock);
    if (stock <= 10) {
        return '<span class="badge low">Pocas unidades</span>';
    }
    return '<span class="badge stock">Disponible</span>';
}

function cardTemplate(item) {
    const colors = splitValues(item.colores).join(", ");
    const imageSrc = `img/${item.modelo}.svg`;
    const modelUrl = `${item.modelo}.html`;

    return `
        <article class="card">
            <img src="${imageSrc}" alt="${item.nombre}" />
            <div class="card-body">
                <div class="badges">
                    <span class="badge">${item.modelo}</span>
                    <span class="badge">${item.tipo_puerta}</span>
                    ${stockBadge(item)}
                </div>
                <h2>${item.nombre}</h2>
                <p>Colores: ${colors}. ${item.disponibilidad}. ${item.observaciones}</p>
                <div class="specs">
                    <div><strong>Dimensiones</strong>${item.ancho_cm} x ${item.alto_cm} x ${item.fondo_cm} cm</div>
                    <div><strong>Baldas</strong>${item.baldas} baldas x ${item.peso_max_por_balda_kg} kg</div>
                    <div><strong>Montaje</strong>${item.montaje_min} min</div>
                    <div><strong>Anclaje</strong>${item.requiere_anclaje_pared}</div>
                </div>
                <div class="card-actions">
                    <div class="price">${item.precio_eur} EUR</div>
                    <a class="btn btn-primary" href="${modelUrl}">Ver modelo</a>
                </div>
            </div>
        </article>
    `;
}

function filterItems(items, query, roomWidth, roomDepth, minShelfLoad) {
    const q = query.trim().toLowerCase();
    return items.filter((item) => {
        const colors = splitValues(item.colores).join(" ").toLowerCase();
        const haystack = `${item.modelo} ${item.nombre} ${item.tipo_puerta} ${item.observaciones} ${colors}`.toLowerCase();

        if (q && !haystack.includes(q)) {
            return false;
        }

        if (roomWidth > 0 && toNumber(item.ancho_cm) > roomWidth) {
            return false;
        }

        if (roomDepth > 0 && toNumber(item.fondo_cm) > roomDepth) {
            return false;
        }

        if (minShelfLoad > 0 && toNumber(item.peso_max_por_balda_kg) < minShelfLoad) {
            return false;
        }

        return true;
    });
}

async function initCatalog() {
    const root = document.getElementById("catalog");
    const count = document.getElementById("catalogCount");
    const inputSearch = document.getElementById("search");
    const inputRoomWidth = document.getElementById("roomWidth");
    const inputRoomDepth = document.getElementById("roomDepth");
    const inputShelfLoad = document.getElementById("shelfLoad");

    try {
        const res = await fetch("catalogo.csv");
        if (!res.ok) {
            throw new Error(`No se pudo cargar el CSV (${res.status})`);
        }
        const csv = await res.text();
        const items = parseCsv(csv);

        function render() {
            const filtered = filterItems(
                items,
                inputSearch.value,
                toNumber(inputRoomWidth.value),
                toNumber(inputRoomDepth.value),
                toNumber(inputShelfLoad.value)
            );

            count.textContent = `${filtered.length} modelos`;

            if (!filtered.length) {
                root.innerHTML = '<div class="empty">No hay armarios con esos filtros. Prueba a ampliar ancho/fondo de habitación o reducir carga por balda.</div>';
                return;
            }

            root.innerHTML = filtered.map(cardTemplate).join("");
        }

        [inputSearch, inputRoomWidth, inputRoomDepth, inputShelfLoad].forEach((el) => {
            el.addEventListener("input", render);
        });

        render();
    } catch (err) {
        root.innerHTML = `<div class="empty">Error cargando catálogo: ${err.message}</div>`;
    }
}

document.addEventListener("DOMContentLoaded", initCatalog);
