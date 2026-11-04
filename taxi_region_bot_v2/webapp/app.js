// Инициализация Telegram Web App
const tg = window.Telegram?.WebApp;
if (tg) {
    tg.ready();
    tg.expand();
}

// Элементы формы
const fromInput = document.getElementById("from");
const toInput = document.getElementById("to");
const swapBtn = document.getElementById("swap-route");
const locationBtn = document.getElementById("location-button");
const locationStatus = document.getElementById("location-status");

const dateInput = document.getElementById("date");
const timeInput = document.getElementById("time");
const quickTimeButtons = document.querySelectorAll(".quick-time-button");

const minusBtn = document.getElementById("minus");
const plusBtn = document.getElementById("plus");
const passengersCount = document.getElementById("passengers");

const paymentOptions = document.querySelectorAll(".payment-option");
const commentTags = document.querySelectorAll(".tag");
const commentInput = document.getElementById("comment");
const orderButton = document.getElementById("order");

// Состояние
let passengers = 1;
let selectedTime = "now";
let selectedPayment = "cash";
let sendingOrder = false;

// Бесплатный ключ Geoapify для обратного геокодирования
// Замените на ваш собственный ключ из файла .env бота при необходимости
const GEOAPIFY_API_KEY = "f5f59fa0fcfb46ac911a300d8cfbdff6";

// ==========================================
// ГЕОЛОКАЦИЯ (HTML5 GPS + Geoapify Reverse)
// ==========================================
async function getLocation() {
    if (!navigator.geolocation) {
        alert("Геолокация не поддерживается вашим браузером");
        return;
    }

    locationBtn.innerText = "⏳";
    locationBtn.disabled = true;
    showLocationStatus("Определяем координаты...");

    navigator.geolocation.getCurrentPosition(
        async (position) => {
            const lat = position.coords.latitude;
            const lon = position.coords.longitude;
            showLocationStatus("Ищем адрес по координатам...");

            try {
                const response = await fetch(
                    `https://api.geoapify.com/v1/geocode/reverse?lat=${lat}&lon=${lon}&apiKey=${GEOAPIFY_API_KEY}&lang=ru`
                );
                const data = await response.json();

                if (data.features && data.features.length > 0) {
                    const props = data.features[0].properties;
                    const street = props.street || "";
                    const housenumber = props.housenumber || "";

                    if (street && housenumber) {
                        fromInput.value = `${street} ${housenumber}`;
                    } else if (props.address_line1) {
                        fromInput.value = props.address_line1;
                    } else {
                        fromInput.value = `${lat.toFixed(5)}, ${lon.toFixed(5)}`;
                    }
                } else {
                    fromInput.value = `${lat.toFixed(5)}, ${lon.toFixed(5)}`;
                }
                showLocationStatus("✅ Адрес успешно определён!");
                setTimeout(() => hideLocationStatus(), 3000);
            } catch (err) {
                console.error("Ошибка геокодирования:", err);
                fromInput.value = `${lat.toFixed(5)}, ${lon.toFixed(5)}`;
                hideLocationStatus();
            } finally {
                locationBtn.innerText = "🎯";
                locationBtn.disabled = false;
                updateOrderButton();
            }
        },
        (error) => {
            locationBtn.innerText = "🎯";
            locationBtn.disabled = false;
            hideLocationStatus();
            if (error.code === error.PERMISSION_DENIED) {
                alert("Пожалуйста, включите GPS и разрешите доступ к геопозиции.");
            } else {
                alert("Не удалось определить местоположение. Введите адрес вручную.");
            }
        },
        { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
    );
}

function showLocationStatus(msg) {
    if (!locationStatus) return;
    locationStatus.innerText = msg;
    locationStatus.style.display = "block";
}

function hideLocationStatus() {
    if (!locationStatus) return;
    locationStatus.style.display = "none";
}

if (locationBtn) {
    locationBtn.addEventListener("click", getLocation);
}

// ==========================================
// ПОМЕНЯТЬ МЕСТАМИ АДРЕСА
// ==========================================
if (swapBtn) {
    swapBtn.addEventListener("click", () => {
        const temp = fromInput.value;
        fromInput.value = toInput.value;
        toInput.value = temp;
        updateOrderButton();
    });
}

// ==========================================
// ПАССАЖИРЫ
// ==========================================
minusBtn.addEventListener("click", () => {
    if (passengers > 1) {
        passengers--;
        passengersCount.innerText = passengers;
    }
});

plusBtn.addEventListener("click", () => {
    if (passengers < 8) {
        passengers++;
        passengersCount.innerText = passengers;
    }
});

// ==========================================
// ВРЕМЯ ПОЕЗДКИ
// ==========================================
function setNow() {
    const now = new Date();
    const pad = (n) => String(n).padStart(2, "0");
    dateInput.value = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
    timeInput.value = `${pad(now.getHours())}:${pad(now.getMinutes())}`;
}

quickTimeButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
        quickTimeButtons.forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        selectedTime = btn.dataset.time;

        const now = new Date();
        const pad = (n) => String(n).padStart(2, "0");

        if (selectedTime === "now") {
            setNow();
        } else if (selectedTime === "30min") {
            const in30 = new Date(now.getTime() + 30 * 60000);
            dateInput.value = `${in30.getFullYear()}-${pad(in30.getMonth() + 1)}-${pad(in30.getDate())}`;
            timeInput.value = `${pad(in30.getHours())}:${pad(in30.getMinutes())}`;
        } else if (selectedTime === "tomorrow") {
            const tomorrow = new Date(now.getTime() + 24 * 3600000);
            dateInput.value = `${tomorrow.getFullYear()}-${pad(tomorrow.getMonth() + 1)}-${pad(tomorrow.getDate())}`;
            timeInput.value = "10:00";
        }
        updateOrderButton();
    });
});

dateInput.addEventListener("change", () => {
    selectedTime = "custom";
    quickTimeButtons.forEach((b) => b.classList.remove("active"));
});

timeInput.addEventListener("change", () => {
    selectedTime = "custom";
    quickTimeButtons.forEach((b) => b.classList.remove("active"));
});

// ==========================================
// СПОСОБ ОПЛАТЫ
// ==========================================
paymentOptions.forEach((btn) => {
    btn.addEventListener("click", () => {
        paymentOptions.forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        selectedPayment = btn.dataset.payment;
    });
});

// ==========================================
// КОММЕНТАРИИ И ТЕГИ
// ==========================================
commentTags.forEach((tag) => {
    tag.addEventListener("click", () => {
        tag.classList.toggle("active");
        updateCommentFromTags();
    });
});

function updateCommentFromTags() {
    const activeTags = [];
    commentTags.forEach((t) => {
        if (t.classList.contains("active")) {
            activeTags.push(t.dataset.comment);
        }
    });

    let current = commentInput.value;
    commentTags.forEach((t) => {
        const val = t.dataset.comment;
        current = current.replace(new RegExp(`,?\\s*${val}`, "gi"), "").trim();
    });

    current = current.replace(/^[,\s]+|[,\s]+$/g, "");
    if (activeTags.length > 0) {
        commentInput.value = activeTags.join(", ") + (current ? `, ${current}` : "");
    } else {
        commentInput.value = current;
    }
}

// ==========================================
// ВАЛИДАЦИЯ И КНОПКА ЗАКАЗА
// ==========================================
function isFormValid() {
    return fromInput.value.trim().length >= 2 && toInput.value.trim().length >= 2;
}

function updateOrderButton() {
    orderButton.disabled = !isFormValid() || sendingOrder;
}

fromInput.addEventListener("input", updateOrderButton);
toInput.addEventListener("input", updateOrderButton);

// ==========================================
// ФОРМИРОВАНИЕ ТЕКСТА ЗАКАЗА ДЛЯ БОТА
// ==========================================
function buildOrderText() {
    const from = fromInput.value.trim();
    const to = toInput.value.trim();
    const date = dateInput.value;
    const time = timeInput.value;
    const comment = commentInput.value.trim();

    let timeText = "сейчас";
    if (selectedTime === "30min") {
        timeText = "через 30 минут";
    } else if (selectedTime === "tomorrow") {
        timeText = `завтра в ${time}`;
    } else if (selectedTime === "custom") {
        timeText = `${date} в ${time}`;
    }

    let text = `${from} — ${to}, ${passengers} человек, ${timeText}`;
    if (comment) {
        text += `, ${comment}`;
    }
    return text;
}

// ==========================================
// ОТПРАВКА ДАННЫХ В БОТА ЧЕРЕЗ TELEGRAM WEB APP
// ==========================================
function sendOrderToBot() {
    if (!isFormValid() || sendingOrder) return;

    const hasChildChair = commentInput.value.toLowerCase().includes("кресл");

    const order = {
        from: fromInput.value.trim(),
        to: toInput.value.trim(),
        passengers: passengers,
        date: dateInput.value,
        time: timeInput.value,
        tariff: "economy",
        payment: selectedPayment,
        has_child_chair: hasChildChair,
        comment: commentInput.value.trim(),
        text: buildOrderText()
    };

    sendingOrder = true;
    orderButton.disabled = true;

    try {
        if (tg) {
            tg.sendData(JSON.stringify(order));
            tg.close();
        } else {
            alert("Telegram WebApp не обнаружен. Откройте приложение внутри Telegram.");
            sendingOrder = false;
            updateOrderButton();
        }
    } catch (err) {
        console.error("Ошибка отправки заказа:", err);
        sendingOrder = false;
        updateOrderButton();
        alert("Не удалось отправить заявку. Попробуйте ещё раз.");
    }
}

orderButton.addEventListener("click", sendOrderToBot);

// Начальное состояние
setNow();
updateOrderButton();