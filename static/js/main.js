
    const priceFormatter = new Intl.NumberFormat('ru-RU', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });

    function formatPrice(value) {
        const num = Number(String(value).replace(/\s+/g, '').replace(',', '.'));
        if (Number.isNaN(num)) return value;
        return priceFormatter.format(num);
    }

    document.addEventListener("DOMContentLoaded", function () {

        // 1. Форматируем все статические цены при загрузке страницы
        document.querySelectorAll(".js-price").forEach(el => {
            const text = el.textContent.trim();
            if (!text || text === "--") return;

            // Отделяем число от валюты (например, "200000,00" и "руб.")
            const match = text.match(/^([\d\s.,]+)\s*(.*)$/);
            if (match) {
                const formattedNum = formatPrice(match[1]);
                const currency = match[2];
                el.textContent = currency ? `${formattedNum} ${currency}` : formattedNum;
            }
        });

    });