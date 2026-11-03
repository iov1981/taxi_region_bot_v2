const tg = window.Telegram.WebApp;

tg.ready();
tg.expand();


// ==========================================
// СОСТОЯНИЕ
// ==========================================

let passengers = 1;

let selectedTime = "now";

let selectedPayment = "cash";

let selectedComments = [];

let sendingOrder = false;


// ==========================================
// ЭЛЕМЕНТЫ
// ==========================================

const fromInput =
    document.getElementById("from");

const toInput =
    document.getElementById("to");

const passengersElement =
    document.getElementById("passengers");

const minusButton =
    document.getElementById("minus");

const plusButton =
    document.getElementById("plus");

const orderButton =
    document.getElementById("order");

const dateInput =
    document.getElementById("date");

const timeInput =
    document.getElementById("time");

const commentInput =
    document.getElementById("comment");

const priceElement =
    document.getElementById("price");

const priceStatus =
    document.getElementById("price-status");

const mapStatus =
    document.getElementById("map-status");


// ==========================================
// TELEGRAM THEME
// ==========================================

function applyTelegramTheme() {

    if (!tg.themeParams) {
        return;
    }

    document.documentElement.style.setProperty(
        "--tg-button-color",
        tg.themeParams.button_color || "#229ed9"
    );
}

applyTelegramTheme();


// ==========================================
// ДАТА
// ==========================================

function formatDate(date) {

    const year =
        date.getFullYear();

    const month =
        String(date.getMonth() + 1)
            .padStart(2, "0");

    const day =
        String(date.getDate())
            .padStart(2, "0");

    return `${year}-${month}-${day}`;
}


// ==========================================
// ВРЕМЯ
// ==========================================

function formatTime(date) {

    const hours =
        String(date.getHours())
            .padStart(2, "0");

    const minutes =
        String(date.getMinutes())
            .padStart(2, "0");

    return `${hours}:${minutes}`;
}


// ==========================================
// СЕЙЧАС
// ==========================================

function setNow() {

    const now =
        new Date();

    dateInput.value =
        formatDate(now);

    timeInput.value =
        formatTime(now);
}


// ==========================================
// ЧЕРЕЗ 30 МИНУТ
// ==========================================

function setThirtyMinutes() {

    const date =
        new Date();

    date.setMinutes(
        date.getMinutes() + 30
    );

    dateInput.value =
        formatDate(date);

    timeInput.value =
        formatTime(date);
}


// ==========================================
// ЗАВТРА
// ==========================================

function setTomorrow() {

    const date =
        new Date();

    date.setDate(
        date.getDate() + 1
    );

    dateInput.value =
        formatDate(date);

    timeInput.value =
        "08:00";
}


// ==========================================
// БЫСТРЫЙ ВЫБОР ВРЕМЕНИ
// ==========================================

document
    .querySelectorAll(".quick-time-button")
    .forEach(button => {

        button.addEventListener(
            "click",
            () => {

                document
                    .querySelectorAll(
                        ".quick-time-button"
                    )
                    .forEach(item => {

                        item.classList.remove(
                            "active"
                        );

                    });

                button.classList.add(
                    "active"
                );

                selectedTime =
                    button.dataset.time;


                if (
                    selectedTime === "now"
                ) {

                    setNow();

                } else if (
                    selectedTime === "30min"
                ) {

                    setThirtyMinutes();

                } else if (
                    selectedTime === "tomorrow"
                ) {

                    setTomorrow();

                }

            }
        );

    });


// ==========================================
// ПАССАЖИРЫ
// ==========================================

minusButton.addEventListener(
    "click",
    () => {

        if (passengers > 1) {

            passengers--;

            passengersElement.textContent =
                passengers;

            updateOrderButton();
        }

    }
);


plusButton.addEventListener(
    "click",
    () => {

        if (passengers < 8) {

            passengers++;

            passengersElement.textContent =
                passengers;

            updateOrderButton();
        }

    }
);


// ==========================================
// ОБМЕН МАРШРУТА
// ==========================================

document
    .getElementById("swap-route")
    .addEventListener(
        "click",
        () => {

            const from =
                fromInput.value;

            const to =
                toInput.value;

            fromInput.value =
                to;

            toInput.value =
                from;

            updateMap();

            updateOrderButton();

        }
    );


// ==========================================
// ГЕОЛОКАЦИЯ
// ==========================================

document
    .getElementById("location-button")
    .addEventListener(
        "click",
        () => {

            const status =
                document.getElementById(
                    "location-status"
                );

            status.classList.remove(
                "hidden"
            );

            status.textContent =
                "Определяем местоположение…";


            if (
                !navigator.geolocation
            ) {

                status.textContent =
                    "Геолокация недоступна на этом устройстве.";

                return;
            }


            navigator.geolocation.getCurrentPosition(

                position => {

                    const latitude =
                        position.coords.latitude;

                    const longitude =
                        position.coords.longitude;


                    window.userLocation = {
                        latitude,
                        longitude
                    };


                    status.textContent =
                        "Местоположение определено.";

                },

                error => {

                    let message =
                        "Не удалось определить местоположение.";


                    if (
                        error.code ===
                        error.PERMISSION_DENIED
                    ) {

                        message =
                            "Доступ к геолокации запрещён.";

                    } else if (
                        error.code ===
                        error.POSITION_UNAVAILABLE
                    ) {

                        message =
                            "Местоположение временно недоступно.";

                    } else if (
                        error.code ===
                        error.TIMEOUT
                    ) {

                        message =
                            "Истекло время определения местоположения.";
                    }


                    status.textContent =
                        message;

                },

                {
                    enableHighAccuracy: true,
                    timeout: 10000,
                    maximumAge: 60000
                }

            );

        }
    );


// ==========================================
// ОПЛАТА
// ==========================================

document
    .querySelectorAll(
        ".payment-option"
    )
    .forEach(button => {

        button.addEventListener(
            "click",
            () => {

                document
                    .querySelectorAll(
                        ".payment-option"
                    )
                    .forEach(item => {

                        item.classList.remove(
                            "active"
                        );

                    });

                button.classList.add(
                    "active"
                );

                selectedPayment =
                    button.dataset.payment;

            }
        );

    });


// ==========================================
// ТЕГИ КОММЕНТАРИЯ
// ==========================================

document
    .querySelectorAll(".tag")
    .forEach(tag => {

        tag.addEventListener(
            "click",
            () => {

                const text =
                    tag.dataset.comment;


                tag.classList.toggle(
                    "active"
                );


                if (
                    selectedComments.includes(
                        text
                    )
                ) {

                    selectedComments =
                        selectedComments.filter(
                            item => item !== text
                        );

                } else {

                    selectedComments.push(
                        text
                    );

                }


                updateCommentField();

            }
        );

    });


function updateCommentField() {

    const customText =
        commentInput.dataset.customText || "";


    const tagsText =
        selectedComments.join(
            ", "
        );


    if (
        tagsText &&
        customText
    ) {

        commentInput.value =
            tagsText +
            ". " +
            customText;

    } else if (
        tagsText
    ) {

        commentInput.value =
            tagsText;

    } else {

        commentInput.value =
            customText;

    }

}


// ==========================================
// РУЧНОЙ КОММЕНТАРИЙ
// ==========================================

commentInput.addEventListener(
    "input",
    () => {

        /*
         * Сохраняем только ручной текст.
         * Теги добавляются отдельно.
         */

        const tagText =
            selectedComments.join(", ");

        let value =
            commentInput.value;

        if (tagText) {

            const prefix =
                tagText + ". ";

            if (
                value.startsWith(prefix)
            ) {

                value =
                    value.substring(
                        prefix.length
                    );

            } else if (
                value === tagText
            ) {

                value = "";
            }
        }

        commentInput.dataset.customText =
            value;

    }
);


// ==========================================
// ОБНОВЛЕНИЕ КАРТЫ-ПРЕВЬЮ
// ==========================================

function updateMap() {

    const from =
        fromInput.value.trim();

    const to =
        toInput.value.trim();


    if (
        from &&
        to
    ) {

        mapStatus.textContent =
            "Маршрут указан. После расчёта координат здесь будет показан фактический маршрут.";

    } else {

        mapStatus.textContent =
            "Введите адреса, чтобы увидеть маршрут.";

    }

}


// ==========================================
// ПРОВЕРКА ФОРМЫ
// ==========================================

function isFormValid() {

    const from =
        fromInput.value.trim();

    const to =
        toInput.value.trim();


    return (
        from.length > 0 &&
        to.length > 0
    );

}


// ==========================================
// ОБНОВЛЕНИЕ КНОПКИ
// ==========================================

function updateOrderButton() {

    const valid =
        isFormValid();


    orderButton.disabled =
        !valid ||
        sendingOrder;


    if (valid) {

        priceStatus.textContent =
            "Стоимость будет рассчитана по маршруту";

    } else {

        priceElement.textContent =
            "—";

        priceStatus.textContent =
            "Введите маршрут для расчёта";

    }


    updateMap();

}


// ==========================================
// ИЗМЕНЕНИЕ АДРЕСА
// ==========================================

fromInput.addEventListener(
    "input",
    updateOrderButton
);

toInput.addEventListener(
    "input",
    updateOrderButton
);


// ==========================================
// ДАТА / ВРЕМЯ
// ==========================================

dateInput.addEventListener(
    "change",
    () => {

        selectedTime =
            "custom";

        document
            .querySelectorAll(
                ".quick-time-button"
            )
            .forEach(item => {

                item.classList.remove(
                    "active"
                );

            });

    }
);


timeInput.addEventListener(
    "change",
    () => {

        selectedTime =
            "custom";

        document
            .querySelectorAll(
                ".quick-time-button"
            )
            .forEach(item => {

                item.classList.remove(
                    "active"
                );

            });

    }
);


// ==========================================
// ПОДГОТОВКА ТЕКСТА ДЛЯ БОТА
// ==========================================

function buildOrderText() {

    const from =
        fromInput.value.trim();

    const to =
        toInput.value.trim();

    const date =
        dateInput.value;

    const time =
        timeInput.value;

    const comment =
        commentInput.value.trim();


    let timeText = "";


    if (selectedTime === "now") {

        timeText =
            "сейчас";

    } else if (
        selectedTime === "30min"
    ) {

        timeText =
            `через 30 минут`;

    } else if (
        selectedTime === "tomorrow"
    ) {

        timeText =
            `завтра в ${time}`;

    } else {

        timeText =
            `${date} в ${time}`;

    }


    let text =
        `${from} — ${to}, ` +
        `${passengers} человек, ` +
        `${timeText}`;


    if (comment) {

        text +=
            `, ${comment}`;

    }


    return text;

}


// ==========================================
// ОТПРАВКА ЗАКАЗА В БОТА
// ==========================================

function sendOrderToBot() {

    if (
        !isFormValid()
    ) {

        return;
    }


    if (sendingOrder) {

        return;
    }


    const orderText =
        buildOrderText();


    const order = {

        from:
            fromInput.value.trim(),

        to:
            toInput.value.trim(),

        passengers:
            passengers,

        date:
            dateInput.value,

        time:
            timeInput.value,

        tariff:
            "economy",

        payment:
            selectedPayment,

        comment:
            commentInput.value.trim(),

        text:
            orderText

    };


    console.log(
        "MINI APP ORDER:",
        order
    );


    sendingOrder = true;

    orderButton.disabled =
        true;


    /*
     * Передаём данные через Telegram.
     *
     * Telegram создаст web_app_data
     * сообщение для нашего бота.
     */

    try {

        tg.sendData(
            JSON.stringify(order)
        );

        /*
         * После sendData Telegram
         * передаст данные боту.
         *
         * Закрываем Mini App.
         */

        tg.close();

    } catch (error) {

        console.error(
            "Ошибка отправки заказа:",
            error
        );

        sendingOrder = false;

        updateOrderButton();

        tg.showAlert(
            "Не удалось отправить заявку.\n\n" +
            "Попробуйте ещё раз."
        );

    }

}


// ==========================================
// КНОПКА ЗАКАЗА
// ==========================================

orderButton.addEventListener(
    "click",
    sendOrderToBot
);


// ==========================================
// НАЧАЛЬНОЕ СОСТОЯНИЕ
// ==========================================

setNow();

updateOrderButton();