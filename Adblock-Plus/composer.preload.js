/******/ (() => { // webpackBootstrap
/******/ 	"use strict";

;// ./src/core/messaging/shared/emitter.ts
class MessageEmitter {
    constructor() {
        this.listeners = new Set();
    }
    addListener(listener) {
        this.listeners.add(listener);
    }
    removeListener(listener) {
        this.listeners.delete(listener);
    }
    dispatch(message, sender) {
        const results = [];
        for (const listener of this.listeners) {
            results.push(listener(message, sender));
        }
        return results;
    }
}

;// ./src/core/messaging/shared/messaging.ts
function getMessageResponse(responses) {
    for (const response of responses) {
        if (typeof response !== "undefined") {
            return response;
        }
    }
}
function isEventMessage(candidate) {
    return isMessage(candidate) && "action" in candidate && "args" in candidate;
}
function isMessage(candidate) {
    return (candidate !== null && typeof candidate === "object" && "type" in candidate);
}
function isListenMessage(candidate) {
    return isMessage(candidate) && "filter" in candidate;
}
function isPremiumActivateOptions(candidate) {
    return (candidate !== null && typeof candidate === "object" && "userId" in candidate);
}
function isPremiumSubscriptionsAddRemoveOptions(candidate) {
    return (candidate !== null &&
        typeof candidate === "object" &&
        "subscriptionType" in candidate);
}

;// ./src/core/messaging/front/messaging.ts

let port;
const connectListeners = new Set();
const disconnectListeners = new Set();
const messageListeners = new Set();
const messageEmitter = new MessageEmitter();
function addConnectListener(listener) {
    connectListeners.add(listener);
    listener();
}
function addDisconnectListener(listener) {
    disconnectListeners.add(listener);
}
function addMessageListener(listener) {
    messageListeners.add(listener);
}
const connect = () => {
    if (port) {
        return port;
    }
    try {
        port = browser.runtime.connect({ name: "ui" });
    }
    catch (ex) {
        port = null;
        disconnectListeners.forEach((listener) => {
            listener();
        });
        return port;
    }
    port.onMessage.addListener((message) => {
        if (!isMessage(message)) {
            return;
        }
        onMessage(message);
    });
    port.onDisconnect.addListener(onDisconnect);
    connectListeners.forEach((listener) => {
        listener();
    });
    return port;
};
function listen({ type, filter, ...options }) {
    addConnectListener(() => {
        if (port) {
            port.postMessage({
                type: `${type}.listen`,
                filter,
                ...options
            });
        }
    });
}
function onDisconnect() {
    port = null;
    setTimeout(() => connect(), 100);
}
function onMessage(message) {
    if (!message.type.endsWith(".respond")) {
        return;
    }
    messageListeners.forEach((listener) => {
        listener(message);
    });
}
function removeDisconnectListener(listener) {
    disconnectListeners.delete(listener);
}
function start() {
    connect();
    if (typeof browser.devtools === "undefined") {
        browser.runtime.onMessage.addListener((message, sender) => {
            if (!isMessage(message)) {
                return;
            }
            const responses = messageEmitter.dispatch(message, sender);
            const response = getMessageResponse(responses);
            if (typeof response === "undefined") {
                return;
            }
            return Promise.resolve(response);
        });
    }
}
start();

;// ./src/core/messaging/front/category-app.ts


const platformToStore = new Map([
    ["chromium", "chrome"],
    ["edgehtml", "edge"],
    ["gecko", "firefox"]
]);
async function get(what) {
    const options = { what };
    return await send("app.get", options);
}
async function getInfo() {
    var _a;
    const [application, platform] = await Promise.all([
        get("application"),
        get("platform")
    ]);
    let store;
    if (application !== "edge" && application !== "opera") {
        store = (_a = platformToStore.get(platform)) !== null && _a !== void 0 ? _a : "chrome";
    }
    else {
        store = application;
    }
    return {
        application,
        manifestVersion: browser.runtime.getManifest().manifest_version,
        platform,
        store
    };
}
function category_app_listen(filter) {
    messaging.listen({ type: "app", filter });
}
async function category_app_open(what, parameters = {}) {
    const options = { what, ...parameters };
    await send("app.open", options);
}

;// ./src/core/messaging/front/category-filters.ts


async function category_filters_get() {
    return await send("filters.get");
}
function category_filters_listen(filter) {
    messaging.listen({ type: "filters", filter });
}

;// ./src/core/messaging/front/category-prefs.ts


async function category_prefs_get(key) {
    const options = { key };
    return await send("prefs.get", options);
}
function category_prefs_listen(filter) {
    messaging.listen({ type: "prefs", filter });
}

;// ./src/core/messaging/front/category-premium.ts


async function activate(userId) {
    const options = { userId };
    return await send("premium.activate", options);
}
async function add(subscriptionType) {
    const options = { subscriptionType };
    await send("premium.subscriptions.add", options);
}
async function category_premium_get() {
    return await send("premium.get");
}
async function getPremiumSubscriptionsState() {
    return await send("premium.subscriptions.getState");
}
function category_premium_listen(filter) {
    messaging.listen({ type: "premium", filter });
}
async function remove(subscriptionType) {
    const options = { subscriptionType };
    await send("premium.subscriptions.remove", options);
}

;// ./src/core/messaging/front/category-requests.ts

function category_requests_listen(filter, tabId) {
    messaging.listen({ type: "requests", filter, tabId });
}

;// ./src/core/messaging/front/category-stats.ts


async function getBlockedPerPage(tab) {
    const options = { tab };
    return await send("stats.getBlockedPerPage", options);
}
async function getBlockedTotal() {
    return await send("stats.getBlockedTotal");
}
function category_stats_listen(filter) {
    messaging.listen({ type: "stats", filter });
}

;// ./src/core/messaging/front/category-subscriptions.ts


async function category_subscriptions_add(url) {
    const options = { url };
    return await send("subscriptions.add", options);
}
async function category_subscriptions_get(options) {
    return await send("subscriptions.get", options !== null && options !== void 0 ? options : {});
}
async function getInitIssues() {
    return await send("subscriptions.getInitIssues");
}
async function getRecommendations() {
    return await send("subscriptions.getRecommendations");
}
function category_subscriptions_listen(filter) {
    messaging.listen({ type: "subscriptions", filter });
}
async function category_subscriptions_remove(url) {
    const options = { url };
    await send("subscriptions.remove", options);
}

;// ./src/core/messaging/front/index.ts



















;// ./src/composer/content/composer.ts

let blockelementPopupId = null;
let currentlyPickingElement = false;
let lastMouseOverEvent = null;
let currentElement = null;
let highlightedElementsSelector = null;
let highlightedElementsInterval = null;
let lastRightClickEvent = null;
let lastRightClickEventIsMostRecent = false;
let keepPreviewEnabled = false;
let previewSelectors = [];
function getURLFromElement(element) {
    if (element.localName === "object") {
        if (element.data) {
            return element.data;
        }
        for (const child of element.children) {
            if (child.localName === "param" &&
                child.name === "movie" &&
                child.value) {
                return new URL(child.value, document.baseURI).href;
            }
        }
        return null;
    }
    return element.currentSrc || element.src;
}
async function getFiltersForElement(element) {
    const src = element.getAttribute("src");
    return await browser.runtime.sendMessage({
        type: "composer.getFilters",
        tagName: element.localName,
        id: element.id,
        src: src && src.length <= 1000 ? src : null,
        style: element.getAttribute("style"),
        classes: Array.prototype.slice.call(element.classList),
        url: getURLFromElement(element)
    });
}
async function getBlockableElementOrAncestor(element) {
    while (element &&
        element !== document.documentElement &&
        element !== document.body) {
        if (!(element instanceof HTMLElement) || element.localName === "area") {
            element = element.parentElement;
        }
        else if (element.localName === "map") {
            const images = document.querySelectorAll("img[usemap]");
            let image = null;
            for (const currentImage of images) {
                const usemap = currentImage.getAttribute("usemap");
                const index = usemap.indexOf("#");
                if (index !== -1 && usemap.substr(index + 1) === element.name) {
                    image = currentImage;
                    break;
                }
            }
            element = image;
        }
        else {
            const { filters } = await getFiltersForElement(element);
            if (filters.length > 0) {
                return element;
            }
            return await getBlockableElementOrAncestor(element.parentElement);
        }
    }
    return null;
}
function addElementOverlay(element) {
    let position = "absolute";
    let offsetX = window.scrollX;
    let offsetY = window.scrollY;
    for (let e = element; e; e = e.parentElement) {
        const style = getComputedStyle(e);
        if (style.display === "none") {
            return null;
        }
        if (style.position === "fixed") {
            position = "fixed";
            offsetX = offsetY = 0;
        }
    }
    const overlay = document.createElement("div");
    overlay.prisoner = element;
    overlay.className = "__adblockplus__overlay";
    overlay.setAttribute("style", "opacity:0.4; display:inline-block !important; " +
        "overflow:hidden; box-sizing:border-box;");
    const rect = element.getBoundingClientRect();
    overlay.style.width = rect.width + "px";
    overlay.style.height = rect.height + "px";
    overlay.style.left = rect.left + offsetX + "px";
    overlay.style.top = rect.top + offsetY + "px";
    overlay.style.position = position;
    overlay.style.zIndex = 0x7ffffffe;
    document.documentElement.appendChild(overlay);
    return overlay;
}
function highlightElement(element, border, backgroundColor) {
    unhighlightElement(element);
    const highlightWithOverlay = () => {
        const overlay = addElementOverlay(element);
        if (!overlay) {
            return;
        }
        highlightElement(overlay, border, backgroundColor);
        overlay.style.pointerEvents = "none";
        element._unhighlight = () => {
            overlay.parentNode.removeChild(overlay);
        };
    };
    const highlightWithStyleAttribute = () => {
        const originalBorder = element.style.getPropertyValue("border");
        const originalBorderPriority = element.style.getPropertyPriority("box-shadow");
        const originalBackgroundColor = element.style.getPropertyValue("background-color");
        const originalBackgroundColorPriority = element.style.getPropertyPriority("background-color");
        element.style.setProperty("border", `2px solid ${border}`, "important");
        element.style.setProperty("background-color", backgroundColor, "important");
        element._unhighlight = () => {
            element.style.removeProperty("box-shadow");
            element.style.setProperty("border", originalBorder, originalBorderPriority);
            element.style.removeProperty("background-color");
            element.style.setProperty("background-color", originalBackgroundColor, originalBackgroundColorPriority);
        };
    };
    if ("prisoner" in element) {
        highlightWithStyleAttribute();
    }
    else {
        highlightWithOverlay();
    }
}
function unhighlightElement(element) {
    if (element && "_unhighlight" in element) {
        element._unhighlight();
        delete element._unhighlight;
    }
}
function highlightElements(selectorString) {
    unhighlightElements();
    const elements = Array.prototype.slice.call(document.querySelectorAll(selectorString));
    highlightedElementsSelector = selectorString;
    highlightedElementsInterval = setInterval(() => {
        if (elements.length > 0) {
            const element = elements.shift();
            if (element !== currentElement) {
                highlightElement(element, "#CA0000", "#CA0000");
            }
        }
        else {
            clearInterval(highlightedElementsInterval);
            highlightedElementsInterval = null;
        }
    }, 0);
}
function unhighlightElements() {
    if (highlightedElementsInterval) {
        clearInterval(highlightedElementsInterval);
        highlightedElementsInterval = null;
    }
    if (highlightedElementsSelector) {
        Array.prototype.forEach.call(document.querySelectorAll(highlightedElementsSelector), unhighlightElement);
        highlightedElementsSelector = null;
    }
}
function stopEventPropagation(event) {
    event.stopPropagation();
}
async function mouseOver(event) {
    lastMouseOverEvent = event;
    const element = await getBlockableElementOrAncestor(event.target);
    if (event === lastMouseOverEvent) {
        lastMouseOverEvent = null;
        if (currentlyPickingElement) {
            if (currentElement) {
                unhighlightElement(currentElement);
            }
            if (element) {
                highlightElement(element, "#CA0000", "#CA0000");
            }
            currentElement = element;
        }
    }
    event.stopPropagation();
}
function mouseOut(event) {
    if (!currentlyPickingElement || currentElement !== event.target) {
        return;
    }
    unhighlightElement(currentElement);
    event.stopPropagation();
}
function keyDown(event) {
    if (!event.ctrlKey && !event.altKey && !event.shiftKey) {
        if (event.keyCode === 13) {
            void elementPicked(event);
        }
        else if (event.keyCode === 27) {
            deactivateBlockElement();
        }
    }
}
function startPickingElement() {
    currentlyPickingElement = true;
    Array.prototype.forEach.call(document.querySelectorAll("object,embed,iframe,frame"), async (element) => {
        const { filters } = await getFiltersForElement(element);
        if (filters.length > 0) {
            addElementOverlay(element);
        }
    });
    document.addEventListener("mousedown", stopEventPropagation, true);
    document.addEventListener("mouseup", stopEventPropagation, true);
    document.addEventListener("mouseenter", stopEventPropagation, true);
    document.addEventListener("mouseleave", stopEventPropagation, true);
    document.addEventListener("mouseover", mouseOver, true);
    document.addEventListener("mouseout", mouseOut, true);
    document.addEventListener("click", elementPicked, true);
    document.addEventListener("contextmenu", elementPicked, true);
    document.addEventListener("keydown", keyDown, true);
    addDisconnectListener(composer_onDisconnect);
}
async function previewBlockedElements(active) {
    if (!currentElement) {
        return;
    }
    const element = currentElement.prisoner || currentElement;
    const overlays = document.querySelectorAll(".__adblockplus__overlay");
    previewBlockedElement(element, active, overlays);
    let selectors;
    if (active) {
        ({ selectors } = await getFiltersForElement(element));
        previewSelectors = selectors;
    }
    else {
        selectors = previewSelectors;
        previewSelectors = [];
    }
    if (selectors.length > 0) {
        const cssQuery = selectors.join(",");
        for (const node of document.querySelectorAll(cssQuery)) {
            previewBlockedElement(node, active, overlays);
        }
    }
}
function previewBlockedElement(element, active, overlays) {
    const display = active ? "none" : null;
    const overlay = Array.prototype.find.call(overlays, ({ prisoner }) => prisoner === element);
    if (overlay) {
        overlay.style.display = display;
    }
    element.style.display = display;
}
async function elementPicked(event) {
    if (!currentElement) {
        return;
    }
    event.preventDefault();
    event.stopPropagation();
    const element = currentElement.prisoner || currentElement;
    const { filters, selectors } = await getFiltersForElement(element);
    if (currentlyPickingElement) {
        stopPickingElement();
    }
    highlightElement(currentElement, "#CA0000", "#CA0000");
    let highlights = 1;
    if (selectors.length > 0) {
        const cssQuery = selectors.join(",");
        highlightElements(cssQuery);
        highlights = document.querySelectorAll(cssQuery).length;
    }
    await browser.runtime.sendMessage({
        type: "composer.openDialog",
        filters,
        highlights
    });
}
function stopPickingElement() {
    currentlyPickingElement = false;
    document.removeEventListener("mousedown", stopEventPropagation, true);
    document.removeEventListener("mouseup", stopEventPropagation, true);
    document.removeEventListener("mouseenter", stopEventPropagation, true);
    document.removeEventListener("mouseleave", stopEventPropagation, true);
    document.removeEventListener("mouseover", mouseOver, true);
    document.removeEventListener("mouseout", mouseOut, true);
    document.removeEventListener("click", elementPicked, true);
    document.removeEventListener("contextmenu", elementPicked, true);
    document.removeEventListener("keydown", keyDown, true);
}
function deactivateBlockElement(popupAlreadyClosed) {
    if (!keepPreviewEnabled) {
        void previewBlockedElements(false);
    }
    if (currentlyPickingElement) {
        stopPickingElement();
    }
    if (blockelementPopupId != null && !popupAlreadyClosed) {
        void browser.runtime.sendMessage({
            type: "composer.forward",
            targetPageId: blockelementPopupId,
            payload: {
                type: "composer.dialog.close"
            }
        });
    }
    blockelementPopupId = null;
    lastRightClickEvent = null;
    if (currentElement) {
        unhighlightElement(currentElement);
        currentElement = null;
    }
    unhighlightElements();
    const overlays = document.getElementsByClassName("__adblockplus__overlay");
    while (overlays.length > 0) {
        overlays[0].parentNode.removeChild(overlays[0]);
    }
    removeDisconnectListener(composer_onDisconnect);
}
function composer_onDisconnect() {
    deactivateBlockElement(true);
}
function initializeComposer() {
    document.addEventListener("contextmenu", (event) => {
        lastRightClickEvent = event;
        lastRightClickEventIsMostRecent = true;
        void browser.runtime.sendMessage({
            type: "composer.forward",
            payload: {
                type: "composer.content.clearPreviousRightClickEvent"
            }
        });
    }, true);
    messageEmitter.addListener((message) => {
        switch (message.type) {
            case "composer.content.preview":
                void previewBlockedElements(message.active);
                break;
            case "composer.content.getState":
                if (window === window.top) {
                    return {
                        active: currentlyPickingElement || blockelementPopupId != null
                    };
                }
                break;
            case "composer.content.startPickingElement":
                if (window === window.top) {
                    startPickingElement();
                }
                break;
            case "composer.content.contextMenuClicked": {
                const event = lastRightClickEvent;
                deactivateBlockElement();
                if (event) {
                    void getBlockableElementOrAncestor(event.target).then((element) => {
                        if (element) {
                            currentElement = element;
                            void elementPicked(event);
                        }
                    });
                }
                break;
            }
            case "composer.content.finished":
                if (currentElement && message.apply) {
                    keepPreviewEnabled = true;
                    void previewBlockedElements(true);
                }
                deactivateBlockElement(!!message.popupAlreadyClosed);
                if (message.reload) {
                    location.reload();
                }
                break;
            case "composer.content.clearPreviousRightClickEvent":
                if (!lastRightClickEventIsMostRecent) {
                    lastRightClickEvent = null;
                }
                lastRightClickEventIsMostRecent = false;
                break;
            case "composer.content.dialogOpened":
                if (window === window.top) {
                    blockelementPopupId = message.popupId;
                }
                break;
            case "composer.content.dialogClosed":
                if (window === window.top && blockelementPopupId === message.popupId) {
                    void browser.runtime.sendMessage({
                        type: "composer.forward",
                        payload: {
                            type: "composer.content.finished",
                            popupAlreadyClosed: true
                        }
                    });
                }
                break;
        }
    });
    if (window === window.top) {
        void browser.runtime.sendMessage({ type: "composer.ready" });
    }
}
function composer_start() {
    if (document instanceof HTMLDocument && location.href !== "about:blank") {
        initializeComposer();
    }
}
composer_start();

;// ./src/composer/content/index.ts


/******/ })()
;
//# sourceMappingURL=composer.preload.js.map