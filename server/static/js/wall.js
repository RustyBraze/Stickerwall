// #############################################################################
// Global Configuration
// #############################################################################
let config = {
    debug:{
        enable: true,
        showWalls: false,
        showBounds: false,
        showLabels: false,
        showWorld: false,
        showStickers: false,
        showStickerSize: false,
        showPhysics: false,
        showSticker: false,
        showStickerVelocity: false,
        showStickerPosition: false,
        colors: {
            walls: '#ee00ff',
            centerWall: '#ff0000',
            bounds: '#00ff00',
            center: '#ff0000',
            text: '#ffffff'
        }
    },

    bot: {
        username: "",
        fullName: ""
    },

    stickers:{
        maxCount: 150,
        maxCountOffset: 20, // offset the total stickers %
        sizeMax: 180,
        sizeMin: 100,
        hitBoxFactor: 0.8,
        physics: {
            enable: true,
            friction: 0.01,
            frictionAir: 0.01,
            restitution: 0.1,
            inertia: 0,
            inverseInertia: 0,
            initialSpeed: 0.2
        }
    },

    world:{
        enableSleeping: true,
        walls:{
            colisionEffectEnable: true,
            forceRestitution: 0,
            enableCentralBlock: true
        },
        gravity:{
            enable: false,
            x: 0,
            y: 0,
            shiftEnable: false,
            shiftTime: 30,
            stopTime: 10,
            shiftFactor: 0.001,
        },
        drift:{
            enable: false,
            force: 0.0005
        }
    },

    animations: {
        flyIn: {
            duration: 1000,  // Duration in ms
            initialScale: 0.1,  // Starting scale
            finalScale: 1,    // Ending scale
            initialAlpha: 0.01, // Starting opacity
            finalAlpha: 1     // Ending opacity
        },
        protection: {
            timeout: 5000,        // Maximum animation duration
            checkInterval: 10000   // How often to check for stuck animations
        }
    },

    mouse: {
        enable: true,
        throwMultiplier: 1,
        constraint: {
            stiffness: 0.1,
            damping: 0,
            visible: true         // Whether to show the constraint line
        }
    }


    };
// #############################################################################

// #############################################################################
// Debug utility
// #############################################################################
const Debug = {
    // Levels of debugging
    LEVELS: {
        ERROR: 'error',
        WARN: 'warn',
        INFO: 'info',
        DEBUG: 'debug'
    },

    // Configuration object
    config: {
        enabled: config.debug.enable,     // Master switch
        level: 'debug',                   // Current level
        prefix: '',                       // Prefix for messages
        // Add specific features flags
        features: {
            messages: true,     // General messages
            network: true,      // Network operations
            physics: true,      // Physics engine related
            stickers: true,     // Sticker operations
            storage: true       // Storage operations
        }
    },

    // Main logging function
    log(feature, level, ...args) {
        // Check if debugging is enabled and the feature is enabled
        if (!this.config.enabled || !this.config.features[feature.toLowerCase()]) {
            return;
        }

        const timestamp = new Date().toISOString().split('T')[1].split('.')[0];
        const prefix = `${this.config.prefix} [${timestamp}] [${feature.toUpperCase()}]`;

        switch (level) {
            case this.LEVELS.ERROR:
                console.error(prefix, ...args);
                break;
            case this.LEVELS.WARN:
                console.warn(prefix, ...args);
                break;
            case this.LEVELS.INFO:
                console.info(prefix, ...args);
                break;
            case this.LEVELS.DEBUG:
                console.debug(prefix, ...args);
                break;
            default:
                console.log(prefix, ...args);
        }
    },

    // Convenience methods
    error(feature, ...args) {
        this.log(feature, this.LEVELS.ERROR, ...args);
    },

    warn(feature, ...args) {
        this.log(feature, this.LEVELS.WARN, ...args);
    },

    info(feature, ...args) {
        this.log(feature, this.LEVELS.INFO, ...args);
    },

    debug(feature, ...args) {
        this.log(feature, this.LEVELS.DEBUG, ...args);
    }
};
// #############################################################################




// We need to use CANVAS and render ourselves the objects with the help from Matter.js
const canvas = document.getElementById('stickerCanvas');
const canvas_context = canvas.getContext('2d');

// Sticker holders
let stickers = []; // holds all stickers
let StickerSize = config.stickers.maxCount; //Actual size of the stickers

// World Walls
let worldWallsCreatedFlag = false;
let worldWalls = [];

let mouse;
let mouseConstraint;







const StorageManager = {
    STORAGE_KEY: 'wall_stickers',

    // Save sticker to localStorage
    saveSticker(sticker) {
        let stickersData = this.getAllStickers();
        stickersData.push({
            id: sticker.id,
            path: sticker.img.src,
            position: sticker.body.position,
            angle: sticker.body.angle,
            velocity: sticker.body.velocity
        });
        localStorage.setItem(this.STORAGE_KEY, JSON.stringify(stickersData));
        Debug.debug('storage', 'Saved sticker:', sticker.id);
    },

    // Remove sticker from localStorage
    removeSticker(stickerId) {
        let stickersData = this.getAllStickers();
        stickersData = stickersData.filter(s => s.id !== stickerId);
        localStorage.setItem(this.STORAGE_KEY, JSON.stringify(stickersData));
        Debug.debug('storage', 'Removed sticker:', stickerId);
    },

    // Get all stored stickers
    getAllStickers() {
        const data = localStorage.getItem(this.STORAGE_KEY);
        return data ? JSON.parse(data) : [];
    },

    // Clear all stickers from storage
    clearStickers() {
        localStorage.removeItem(this.STORAGE_KEY);
        Debug.info('storage', 'Cleared all stickers from storage');
    }
};


const AnimationManager = {
    animatingStickers: new Map(),

    startAnimation(sticker) {
        const startTime = performance.now();
        this.animatingStickers.set(sticker.id, {
            startTime,
            initialPosition: { ...sticker.body.position },
            initialScale: config.animations.flyIn.initialScale,
            lastUpdateTime: startTime,
            isAnimating: true
        });
    },

    updateAnimations(currentTime) {
        this.animatingStickers.forEach((animation, stickerId) => {
            const sticker = stickers.find(s => s.id === stickerId);
            if (!sticker) {
                this.animatingStickers.delete(stickerId);
                Debug.warn('animations', `Sticker not found, removing animation: ${stickerId}`);
                return;
            }

            const elapsed = currentTime - animation.startTime;
            const timeSinceLastUpdate = currentTime - animation.lastUpdateTime;

            // Check for stuck animations
            if (elapsed >= config.animations.protection.timeout) {
                Debug.warn('animations', `Animation timeout for sticker: ${stickerId}`);
                this.forceCompleteAnimation(sticker);
                return;
            }

            // Check for no updates
            if (timeSinceLastUpdate > config.animations.protection.checkInterval) {
                if (sticker.scale !== 1 || sticker.alpha !== 1) {
                    Debug.warn('animations', `Possible stuck animation detected for sticker: ${stickerId}`);
                    this.forceCompleteAnimation(sticker);
                    return;
                }
            }

            const progress = Math.min(elapsed / config.animations.flyIn.duration, 1);
            // Ease function (smooth start and end)
            const eased = this.easeInOutQuad(progress);

            // // Update scale and alpha
            // sticker.scale = this.lerp(
            //     config.animations.flyIn.initialScale,
            //     config.animations.flyIn.finalScale,
            //     eased
            // );
            //
            // sticker.alpha = this.lerp(
            //     config.animations.flyIn.initialAlpha,
            //     config.animations.flyIn.finalAlpha,
            //     eased
            // );

            // Update scale and alpha
            const newScale = this.lerp(
                config.animations.flyIn.initialScale,
                config.animations.flyIn.finalScale,
                eased
            );
            const newAlpha = this.lerp(
                config.animations.flyIn.initialAlpha,
                config.animations.flyIn.finalAlpha,
                eased
            );

            // Only update if values have changed
            if (sticker.scale !== newScale || sticker.alpha !== newAlpha) {
                sticker.scale = newScale;
                sticker.alpha = newAlpha;
                animation.lastUpdateTime = currentTime;
            }

            // If animation is complete, remove from tracking
            if (progress >= 1) {
                this.animatingStickers.delete(stickerId);
            }
        });
    },

    completeAnimation(sticker) {
        if (this.animatingStickers.has(sticker.id)) {
            sticker.scale = config.animations.flyIn.finalScale;
            sticker.alpha = config.animations.flyIn.finalAlpha;
            this.animatingStickers.delete(sticker.id);
            Debug.debug('animations', `Animation completed normally for sticker: ${sticker.id}`);
        }
    },

    forceCompleteAnimation(sticker) {
        sticker.scale = config.animations.flyIn.finalScale;
        sticker.alpha = config.animations.flyIn.finalAlpha;
        this.animatingStickers.delete(sticker.id);
        Debug.warn('animations', `Forced animation completion for sticker: ${sticker.id}`);
    },

    // Add a method to check all stickers for potential stuck states
    checkAllStickers() {
        stickers.forEach(sticker => {
            if (sticker.scale !== config.animations.flyIn.finalScale ||
                sticker.alpha !== config.animations.flyIn.finalAlpha) {
                Debug.warn('animations', `Found stuck sticker: ${sticker.id}, forcing completion`);
                this.forceCompleteAnimation(sticker);
                // this.startAnimation(sticker);
            }
        });
    },

    // Utility functions
    lerp(start, end, t) {
        return start * (1 - t) + end * t;
    },

    easeInOutQuad(t) {
        return t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
    }
};


const StickerManager = {
    hasSticker(stickerId) {
        return stickers.some(sticker => sticker.id === stickerId);
    },

    removeSticker(stickerId) {
        const index = stickers.findIndex(sticker => sticker.id === stickerId);
        if (index !== -1) {
            const sticker = stickers[index];
            Composite.remove(engine.world, sticker.body);
            stickers.splice(index, 1);
            StorageManager.removeSticker(stickerId);
            return true;
        }
        return false;
    }
};


// #############################################################################
// Websock class
// #############################################################################
class WebSocketClient {
    constructor() {
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 99999;
        this.reconnectDelay = 1000; // Start with 1 second
        this.messageDiv = document.getElementById('messageDIV');
        this.messageCard = document.getElementById('messageCard');
        this.connect();
    }

    updateMessage(message, isConnecting = false) {
        // if (this.messageDiv) {
        if (this.messageCard) {

            if (isConnecting) {
                // this.messageDiv.innerHTML = `
                this.messageCard.innerHTML = `
                    <div class="com-info">
                        <p>
                            <strong>Almost there...</strong>
                            <br>
                            ${message}
                        </p>
                    </div>`;
            } else {
                // this.messageDiv.innerHTML = `
                //     <p>
                //         Sticker Party!<br>
                //         <strong>${message}</strong>
                //     </p>`;

                // Clear previous content
                // this.messageDiv.innerHTML = '';
                this.messageCard.innerHTML = '';

                // Create title
                // const titleDiv = document.createElement('div');
                // titleDiv.textContent = 'Sticker Wall';
                // // titleDiv.style.width = '200px'
                // titleDiv.style.fontSize = '24px';
                // titleDiv.style.marginTop = '5px';
                // titleDiv.style.marginBottom = '10px';
                // titleDiv.style.fontWeight = 'bold';
                const textDiv = document.createElement('div');
                textDiv.classList.add('text-content');

                const titleH1 = document.createElement('h1');
                titleH1.textContent = 'sticker wall';

                const textP = document.createElement('p');
                // textP.textContent = `send your sticker to<br>@${config.bot.username}`;
                textP.innerHTML = `send your sticker to<br>@${config.bot.username}`;

                textDiv.appendChild(titleH1);
                textDiv.appendChild(textP);

                const qrDiv = document.createElement('div');
                qrDiv.classList.add('qr-container');
                qrDiv.id = 'qrcode';

                this.messageCard.appendChild(textDiv);
                this.messageCard.appendChild(qrDiv);



                // // Create QR code container
                // const qrDiv = document.createElement('div');
                // qrDiv.id = 'qrcode';
                //
                // // Create bot handle text
                // const handleDiv = document.createElement('div');
                // handleDiv.textContent = `@${config.bot.username}`;
                // handleDiv.style.marginTop = '5px';
                // handleDiv.style.fontSize = '16px';
                //
                // // Add all elements to message div
                // this.messageDiv.appendChild(titleDiv);
                // this.messageDiv.appendChild(qrDiv);
                // this.messageDiv.appendChild(handleDiv);
                //
                // Generate QR code
                const botHandle = `https://t.me/${config.bot.username}`;
                new QRCode(document.getElementById("qrcode"), {
                    text: botHandle,
                    width: 100,
                    height: 100,
                    colorDark: "#000000",
                    colorLight: "#ffffff",
                    correctLevel: QRCode.CorrectLevel.H
                });
                //
                // // Center align all content
                // this.messageDiv.style.textAlign = 'center';
                //
                // // Style QR code container
                // const qrContainer = document.getElementById('qrcode');
                // qrContainer.style.display = 'flex';
                // qrContainer.style.justifyContent = 'center';
                // qrContainer.style.margin = '0 auto';



            }
        }
    }

    getWebSocketUrl() {
        const hostname = window.location.hostname;
        const port = window.location.port;
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';

        if (!hostname || hostname === 'localhost' || hostname === '127.0.0.1') {
            return 'ws://127.0.0.1:8000/ws/wall';
        }

        // If there's a specific port, use it; otherwise don't include port in the URL
        if (port) {
            return `${protocol}//${hostname}:${port}/ws/wall`;
        } else {
            return `${protocol}//${hostname}/ws/wall`;
        }
    }

    connect() {
        this.updateMessage("Please wait...", true);
        this.ws = new WebSocket(this.getWebSocketUrl());

        this.ws.onopen = () => {
            Debug.info('network', 'WebSocket Connected');
            this.reconnectAttempts = 0;
            this.reconnectDelay = 1000;
            // Request bot info when connected
            this.ws.send(JSON.stringify({ type: 'get_bot_info' }));
        };

        this.ws.onclose = () => {
            if (this.reconnectAttempts < this.maxReconnectAttempts) {
                // Debug.warn('network', `WebSocket Reconnecting... Attempt ${this.reconnectAttempts + 1} - Wait: ${this.reconnectDelay * 2}`);
                Debug.warn('network', `WebSocket Reconnecting... Attempt ${this.reconnectAttempts + 1} - Wait: ${this.reconnectDelay + 250}`);
                this.updateMessage("Reconnecting to server...", true);
                setTimeout(() => this.connect(), this.reconnectDelay);
                this.reconnectAttempts++;
                // this.reconnectDelay *= 1.2; // Exponential backoff
                this.reconnectDelay += 250; // Exponential backoff
            } else {
                Debug.error('network','WebSocket Failed to connect after maximum attempts');
                this.updateMessage("Failed to connect to server", true);
            }
        };

        this.ws.onerror = (error) => {
            Debug.error('network','WebSocket Error:', error);
            this.updateMessage("Connection error", true);
        };

        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                Debug.debug('network','Received message:', data);

                switch (data.type) {
                    case 'bot_info':
                        Debug.debug('network', 'BOT Information:', data.data);
                        // Update the message div with bot username
                        if (data.data.username) {
                            config.bot.username = data.data.username;
                            config.bot.fullName = data.data.full_name || data.data.username;
                            this.updateMessage(`@${data.data.username}`);
                        }
                        break;

                    case 'wall_clear':
                        // Remove all stickers from the wall
                        removeAllStickers();
                        break;

                    case 'wall_reload':
                        // This is handled automatically by the sequence of clear + sticker_add messages
                        break;

                    case 'sticker_add':
                        // Check if sticker already exists
                        if (StickerManager.hasSticker(data.data.sticker_id)) {
                            Debug.warn('stickers', `Duplicate sticker ignored: ${data.data.sticker_id}`);
                            return;
                        }
                        Debug.debug('network','Adding new sticker:', data.data.path);
                        addSticker(data.data.path, data.data.sticker_id);
                        break;

                    case 'sticker_remove':
                        // Remove sticker from the wall
                        Debug.debug('network','Removing sticker:', data.data.sticker_id);
                        removeSticker(data.data.sticker_id);
                        // StickerManager.removeSticker(data.sticker_id);
                        break;

                    case 'wall_sync':
                        Debug.debug('network','Sync requested - waiting 10 seconds before executing');
                        setTimeout(() => {
                            handleWallSync(data);
                        }, 10000);
                        // handleWallSync(data);
                        break;

                    // case 'bot_info':
                    //     // Remove sticker from the wall
                    //     Debug.debug('network','BOT Information:', data.data);
                    //     // removeSticker(data.data.sticker_id);
                    //     // StickerManager.removeSticker(data.sticker_id);
                    //     break;

                    default:
                        Debug.warn('network','Unknown sticker action:', data.type);
                        Debug.debug('network','Unknown received message:', data);
                }

            } catch (error) {
                // Handle legacy string messages (backward compatibility)
                // Debug.debug('network','Received legacy message:', event.data);
                // addSticker(event.data);
                Debug.error('network', 'Error processing message:', error);
            }
        };
    }

    // // Method to send messages
    // send(data) {
    //     if (this.ws.readyState === WebSocket.OPEN) {
    //         this.ws.send(data);
    //     } else {
    //         console.error('WebSocket is not connected');
    //     }
    // }

    // wsClient.onmessage = (event) => {
    // };

}
// #############################################################################



















// #############################################################################
// Matter.js Stuff + World stuff
// #############################################################################
// -----------------------------------------------------------------------------
// Modules aliases
const Engine = Matter.Engine,
    // Render = Matter.Render,
    Runner = Matter.Runner,
    Bodies = Matter.Bodies,
    Composite = Matter.Composite,
    Events = Matter.Events;

// -----------------------------------------------------------------------------
// create the engine
const engine = Engine.create(
    {
        enableSleeping: config.world.enableSleeping,
        // positionIterations: 6,
        // velocityIterations: 6
    }
);


// #############################################################################
// Functions
// #############################################################################


// -----------------------------------------------------------------------------
// Canvas Size
// -----------------------------------------------------------------------------
function resizeCanvas() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    Debug.debug('messages', 'Canvas Size set:', canvas.width, canvas.height);

    // const infoBox = document.getElementById('messageDIV');
    // infoBox.innerHTML = `Canvas Size: ${canvas.width}x${canvas.height}.${window.devicePixelRatio}`;

    if (worldWallsCreatedFlag) {
        createWalls();
    }
}
// Add Event
window.addEventListener('resize', resizeCanvas);
// Trigger now the function because of reasons
resizeCanvas();
// -----------------------------------------------------------------------------

// -----------------------------------------------------------------------------
const RotationManager = {
    lastValue: null,

    getRandomRotation() {
        // Generate a value between 0 and 0.1
        let value = (Math.random() * 0.2).toFixed(3);

        // If this is the first call or last value was negative, make it positive
        if (this.lastValue === null || this.lastValue < 0) {
            value = Math.abs(value);
        } else {
            // If last value was positive, make this one negative
            value = -Math.abs(value);
        }

        // Store this value for next call
        this.lastValue = parseFloat(value);

        Debug.debug('physics', "Random rotation value:", this.lastValue);
        return this.lastValue;
    }
};
// -----------------------------------------------------------------------------



// -----------------------------------------------------------------------------
// World Walls
// -----------------------------------------------------------------------------
function createWalls() {

    if (worldWallsCreatedFlag) {
        Composite.remove(engine.world, worldWalls);
        worldWalls = [];
    }

    const WallGroundBottom = Bodies.rectangle(canvas.width / 2, canvas.height, canvas.width, 50, { label:"groundBottom", isStatic: true, restitution: config.world.walls.forceRestitution });
    const WallGroundtop = Bodies.rectangle(canvas.width / 2, 0, canvas.width, 50, { label: "groundTop", isStatic: true, restitution: config.world.walls.forceRestitution });
    const WallGroundRight = Bodies.rectangle(canvas.width, canvas.height / 2, 50, canvas.height, { label: "groundRight", isStatic: true, restitution: config.world.walls.forceRestitution });
    const WallGroundLeft = Bodies.rectangle(0, canvas.height / 2, 50, canvas.height, { label: "groundLeft", isStatic: true, restitution: config.world.walls.forceRestitution });
    // const WallCenterBlock = Bodies.rectangle(canvas.width / 2, canvas.height / 2, canvas.width / 4, 50, { label: "centerBlock", isStatic: true, restitution: config.world.walls.forceRestitution });
    const WallCenterBlock = Bodies.rectangle(canvas.width / 2, canvas.height / 2, 290, 120, { label: "centerBlock", isStatic: true, restitution: config.world.walls.forceRestitution });

    worldWalls.push(WallGroundBottom);
    worldWalls.push(WallGroundtop);
    worldWalls.push(WallGroundRight);
    worldWalls.push(WallGroundLeft);

    if (config.world.walls.enableCentralBlock) {
        worldWalls.push(WallCenterBlock);
    }

    Composite.add(engine.world, worldWalls);

    worldWallsCreatedFlag = true;
    Debug.debug('messages', "Walls created");
}
createWalls();
// -----------------------------------------------------------------------------

// -----------------------------------------------------------------------------
// function getRandomVelocity() {
//     const precision = 1000; // Adjust for more or fewer decimal places
//     const value = Math.floor(Math.random() * (precision * 2 + 1) - precision) / precision;
//     // Debug.debug('physics', "Random value: ", value);
//     return value;
// }
// -----------------------------------------------------------------------------

// function getRandomRotation() {
//     // const precision = 100; // Adjust for more or fewer decimal places
//     // const value = Math.floor(Math.random() * (precision * 2 + 1) - precision) / precision;
//     // Debug.debug('physics', "Random value: ", value);
//     // return value;
//     return parseFloat(((Math.random() * 0.1) - 0.1).toFixed(3));
// }

// ------------------------------------------------------------------------------------
/**
 * Generates a random integer between the specified minimum and maximum values, inclusive.
 *
 * @param {number} min - The minimum value of the interval.
 * @param {number} max - The maximum value of the interval.
 * @return {number} A random integer between min and max, inclusive.
 */
function randomIntFromInterval(min, max) { // min and max included
    return Math.floor(Math.random() * (max - min + 1) + min);
}
// -----------------------------------------------------------------------------

// -----------------------------------------------------------------------------
/**
 * Calculates new dimensions for an image while maintaining aspect ratio
 * @param {number} originalWidth - The original width of the image
 * @param {number} originalHeight - The original height of the image
 * @param {number} maxSize - The maximum allowed width or height
 * @returns {{width: number, height: number}} New dimensions object
 */
function calculateProportionalSize(originalWidth, originalHeight, maxSize) {
    let newWidth, newHeight;

    if (originalWidth > originalHeight) {
        // Image is wider than it is tall
        newWidth = maxSize;
        newHeight = (originalHeight / originalWidth) * maxSize;
    } else {
        // Image is taller than it is wide or square
        newHeight = maxSize;
        newWidth = (originalWidth / originalHeight) * maxSize;
    }

    return {
        width: Math.round(newWidth),
        height: Math.round(newHeight)
    };
}
// -----------------------------------------------------------------------------


// -----------------------------------------------------------------------------
/**
 * Calculates the size of stickers based on the current number of stickers
 * and a predefined limit. The size is determined using linear interpolation
 * between a maximum and minimum size, inversely proportional to the ratio
 * of stickers to the limit.
 *
 * @return {void} updates the global variable.
 */
function calculateStickerSize() {
    // Get percentage of stickers compared to limit
    const stickerPercentage = Math.min(stickers.length / (config.stickers.maxCount - config.stickers.maxCountOffset), 1);

    // Calculate size using linear interpolation between max and min
    StickerSize = Math.round(config.stickers.sizeMax - (stickerPercentage * (config.stickers.sizeMax - config.stickers.sizeMin)));
    Debug.debug('stickers', "Sticker percentage: ", stickerPercentage, " Sticker size: ", StickerSize);
}
// -----------------------------------------------------------------------------

// -----------------------------------------------------------------------------
/**
 * Updates the sizes of all sticker bodies in the physics engine to match a proportional size calculation.
 * Applies changes while preserving each body's position, angle, and velocity.
 *
 * @return {void} No return value.
 */
function updateAllStickerBodiesSizes() {
    // Get all non-static bodies from the world
    const bodies = Composite.allBodies(engine.world).filter(body => !body.isStatic);

    // Update each sticker's body
    stickers.forEach((sticker, index) => {
        if (index >= bodies.length) return;

        // Calculate new proportional size for the sticker
        const corrected_size = calculateProportionalSize(
            sticker.img.width,
            sticker.img.height,
            (StickerSize * config.stickers.hitBoxFactor)
        );

        // Store current position and velocity
        const position = { ...sticker.body.position };
        const velocity = { ...sticker.body.velocity };
        const angle = sticker.body.angle;

        // Remove old body
        Composite.remove(engine.world, sticker.body);

        // Create new body with updated size
        const newBody = Bodies.rectangle(
            position.x,
            position.y,
            corrected_size.width,
            corrected_size.height,
            {
                restitution: config.stickers.physics.restitution,            // Perfect bounce
                frictionAir: config.stickers.physics.frictionAir,            // No air friction
                friction: config.stickers.physics.friction,                  // No surface friction
                inertia: Infinity,                                           // Prevent rotation
                inverseInertia: config.stickers.physics.inverseInertia       // Prevent rotation
            }
        );

        // Restore position, angle and velocity
        Matter.Body.setPosition(newBody, position);
        Matter.Body.setAngle(newBody, angle);
        Matter.Body.setVelocity(newBody, velocity);

        // Add new body to world
        Composite.add(engine.world, newBody);

        // Update sticker reference
        sticker.body = newBody;
    });
}
// -----------------------------------------------------------------------------

// -----------------------------------------------------------------------------
/**
 * Adds a sticker to the canvas at a random position, with a calculated size and initial velocity.
 * The sticker is dynamically added to the physics engine and managed within a sticker limit.
 * If the limit is exceeded, the oldest sticker is removed to make room for the new one.
 *
 * @param {string} stickerPath - The path to the image file used as the sticker.
 * @param {string} stickerId - Sticker String ID.
 * @return {void} This method does not return a value.
 */
function addSticker(stickerPath,stickerId) {

    if (StickerManager.hasSticker(stickerId)) {
        Debug.warn('stickers', `Attempt to add duplicate sticker: ${stickerId}`);
        return;
    }

    // const startingX = Math.random() * (canvas.width);
    // const startingY = Math.random() * (canvas.height);

    // Calculate starting position outside the screen
    const side = Math.floor(Math.random() * 4); // 0: top, 1: right, 2: bottom, 3: left
    let startingX, startingY;

    switch(side) {
        case 0: // top
            startingX = Math.random() * canvas.width;
            startingY = 100;
            break;
        case 1: // right
            startingX = canvas.width - 100;
            startingY = Math.random() * canvas.height;
            break;
        case 2: // bottom
            startingX = Math.random() * canvas.width;
            startingY = canvas.height - 100;
            break;
        case 3: // left
            startingX = 100;
            startingY = Math.random() * canvas.height;
            break;
    }

    Debug.debug('stickers', "Starting position: ", startingX, startingY);

    const img = new Image();

    img.src = stickerPath;

    img.onload = () => {
        // update next sticker size
        calculateStickerSize();
        // Update all sizes
        updateAllStickerBodiesSizes();

        // Set a random location to start
        const x = startingX;
        const y = startingY;

        const corrected_size = calculateProportionalSize(
            img.width,
            img.height,
            (StickerSize * config.stickers.hitBoxFactor)
        );

        const body = Bodies.rectangle(x, y, corrected_size.width, corrected_size.height, {
                restitution: config.stickers.physics.restitution,            // Perfect bounce
                frictionAir: config.stickers.physics.frictionAir,            // No air friction
                friction: config.stickers.physics.friction,                  // No surface friction
                inertia: Infinity,                                           // Prevent rotation
                inverseInertia: config.stickers.physics.inverseInertia       // Prevent rotation
            }
        );

        // // Set initial velocity
        // const speed = config.stickers.physics.initialSpeed; // Consistent initial speed
        // const randomAngle = Math.random() * Math.PI * 2;
        // Matter.Body.setVelocity(body, {
        //     x: Math.cos(randomAngle) * speed,
        //     y: Math.sin(randomAngle) * speed
        // });

        // Calculate velocity towards center of screen
        const targetX = canvas.width / 2;
        const targetY = canvas.height / 2;
        const angle = Math.atan2(targetY - startingY, targetX - startingX);
        const speed = config.stickers.physics.initialSpeed; // Increased initial speed for animation

        Matter.Body.setVelocity(body, {
            x: Math.cos(angle) * speed,
            y: Math.sin(angle) * speed
        });

        // Matter.Body.rotate(body, (Math.random() * 0.5) - 0.2);
        Matter.Body.setAngle(body, RotationManager.getRandomRotation());
        // Matter.Body.setAngle(body, 0.2);

        Debug.debug("messages","Created sticker at: ", x, y, " with angle: ", angle, " and speed: ", speed, "");

        // World.add(engine.world, body);
        Composite.add(engine.world, body);

        const stickerObj = {
            id: stickerId,
            img: img,
            body: body,
            scale: config.animations.flyIn.initialScale,
            alpha: config.animations.flyIn.initialAlpha
        };

        stickers.push(stickerObj);
        StorageManager.saveSticker(stickerObj);

        // // stickers.push({ img: img, body: body });
        // stickers.push({
        //     id: stickerId,
        //     img: img,
        //     body: body
        // });

        // localStorage.setItem('stickers', JSON.stringify({
        //     body: body
        // }));

        // Start animation
        AnimationManager.startAnimation(stickerObj);
    };

    if (stickers.length > config.stickers.maxCount) {
        const oldSticker = stickers.shift();
        Composite.remove(engine.world, oldSticker.body);
        StorageManager.removeSticker(oldSticker.id);
    }

    // Debug.debug('stickers', "Function complete");
}
// -----------------------------------------------------------------------------

// -----------------------------------------------------------------------------
function removeSticker(stickerId) {
    // Find the sticker index with matching ID
    const index = stickers.findIndex(sticker => sticker.id === stickerId);

    if (index !== -1) {
        // Remove the body from the physics world
        Composite.remove(engine.world, stickers[index].body);

        // Remove the sticker from our array
        stickers.splice(index, 1);

        // Remove from storage
        StorageManager.removeSticker(stickerId);

        // Recalculate sizes for remaining stickers
        calculateStickerSize();
        updateAllStickerBodiesSizes();

        Debug.debug('stickers',`Removed sticker: ${stickerId}`);
    }
}
// -----------------------------------------------------------------------------

// -----------------------------------------------------------------------------
function restoreStickers() {
    const storedStickers = StorageManager.getAllStickers();

    Debug.info('storage', `Restoring ${storedStickers.length} stickers`);

    // Clear existing stickers first
    removeAllStickers();

    // Restore stickers
    storedStickers.forEach(storedSticker => {
        addSticker(storedSticker.path, storedSticker.id);
    });
}
// -----------------------------------------------------------------------------

// -----------------------------------------------------------------------------
function removeAllStickers() {
    // Composite.allBodies(engine.world).forEach(body => {
    //
    //     if (body.isStatic) return;
    //     Composite.remove(engine.world, body);
    // });

    stickers.forEach(sticker => {
        Matter.World.remove(engine.world, sticker.body);
    });

    stickers = [];
    StorageManager.clearStickers();
}
// -----------------------------------------------------------------------------

// -----------------------------------------------------------------------------
// Function to get a random gravity value between -0.1 and 0.1
function getRandomGravity() {
    return (Math.random() * 0.1) - 0.1;
}

// Function to reset gravity to zero
function resetGravity() {
    engine.world.gravity.x = config.world.gravity.x;
    engine.world.gravity.y = config.world.gravity.y;

    // engine.timing.timeScale = 0.1;
    // engine.gravity.scale = 0.0001;

    Debug.debug('physics', "Gravity back to default");
}

// Function to apply random gravity
function applyRandomGravity() {
    Debug.debug('physics', "Applying random gravity");

    const gravity = getRandomGravity();

    engine.world.gravity.x = gravity;
    engine.world.gravity.y = gravity * -1;

    // Reset gravity after a few seconds
    setTimeout(resetGravity, 10000);
}
// -----------------------------------------------------------------------------

function toggleFullScreen() {
    if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen();
    } else if (document.exitFullscreen) {
        document.exitFullscreen();
    }
    Debug.debug('messages', "Functions loaded");
}// -----------------------------------------------------------------------------
// toggleFullScreen();

// -----------------------------------------------------------------------------
function initializeMouseInteraction() {
    // Add mouse control
    mouse = Matter.Mouse.create(canvas);
    // mouse.pixelRatio = window.devicePixelRatio; // Handle high DPI displays
    mouse.pixelRatio = 1

    // Create the mouse constraint
    mouseConstraint = Matter.MouseConstraint.create(engine, {
        mouse: mouse,
        throwMultiplier: config.mouse.constraint.throwMultiplier,
        constraint: {
            stiffness: config.mouse.constraint.stiffness,
            damping: config.mouse.constraint.damping,
            render: {
                visible: false
            }
        }
    });

    // Add mouse constraint to world
    Matter.Composite.add(engine.world, mouseConstraint);

    // Add mouse interaction events
    Matter.Events.on(mouseConstraint, 'mousedown', function(event) {
        const mousePosition = event.mouse.position;
        Debug.debug('physics', 'Mouse down at:', mousePosition);
    });

    Matter.Events.on(mouseConstraint, 'mousemove', function(event) {
        // Optional: Handle mouse movement
    });

    Matter.Events.on(mouseConstraint, 'mouseup', function(event) {
        // Optional: Handle mouse release
        const mousePosition = event.mouse.position;
        Debug.debug('physics', 'Mouse up at:', mousePosition);
    });

    // Add movement multiplier for "throwing" stickers
    Matter.Events.on(mouseConstraint, 'enddrag', function(event) {
        if (event.body) {
            // Increase the velocity after dragging
            const velocityMultiplier = 1.5; // Adjust this value to change throw strength
            Matter.Body.setVelocity(event.body, {
                x: event.body.velocity.x * velocityMultiplier,
                y: event.body.velocity.y * velocityMultiplier
            });
        }
    });

    // Prevent page scrolling when interacting with canvas
    canvas.addEventListener('mousewheel', function(event) {
        event.preventDefault();
    });

    canvas.addEventListener('touchmove', function(event) {
        event.preventDefault();
    }, { passive: false });
}
// -----------------------------------------------------------------------------

// -----------------------------------------------------------------------------
function toggleMouseInteraction(enable) {
    if (enable && !mouseConstraint) {
        initializeMouseInteraction();
    } else if (!enable && mouseConstraint) {
        Matter.Composite.remove(engine.world, mouseConstraint);
        mouseConstraint = null;
    }
    config.mouse.enable = enable;
}
// -----------------------------------------------------------------------------

// -----------------------------------------------------------------------------
function handleWallSync(message) {
    Debug.info('network', `Running Sync feature now...`);

    const serverStickers = message.data;
    const serverStickerIds = new Set(serverStickers.map(s => s.sticker_id));

    // Remove stickers that are not in the server list
    stickers = stickers.filter(sticker => {
        if (!serverStickerIds.has(sticker.id)) {


        //     addSticker(data.data.path, data.data.sticker_id);
        //     break;
        //
        // case 'sticker_remove':
        //     // Remove sticker from the wall
        //     Debug.debug('network','Removing sticker:', data.data.sticker_id);
        //     removeSticker(data.data.sticker_id);
            removeSticker(sticker.id);

            // // Remove from physics world
            // World.remove(engine.world, sticker.body);
            // // Remove from storage
            // StorageManager.removeSticker();
            Debug.info('network', `Removed sticker not in sync: ${sticker.id}`);
            return false;
        }
        return true;
    });

    // Add new stickers from server that don't exist locally
    serverStickers.forEach(serverSticker => {
        const exists = stickers.some(s => s.id === serverSticker.sticker_id);
        if (!exists) {
            addSticker(serverSticker.path, serverSticker.sticker_id)

            // // Create new sticker
            // const sticker = createSticker(
            //     serverSticker.sticker_id,
            //     serverSticker.path,
            //     { x: Math.random() * canvas.width, y: Math.random() * canvas.height },
            //     serverSticker.boost_factor
            // );
            //
            // // Add to physics world
            // World.add(engine.world, sticker.body);
            // // Add to stickers array
            // stickers.push(sticker);
            // // Start animation for new sticker
            // AnimationManager.startAnimation(sticker);

            Debug.info('network', `Added new sticker from sync: ${serverSticker.sticker_id}`);
        }
    });
}
// -----------------------------------------------------------------------------


// -----------------------------------------------------------------------------
// -----------------------------------------------------------------------------
// -----------------------------------------------------------------------------
/**
 * Animation Render Loop
 *
 * A self-executing function that handles the continuous rendering of stickers on the canvas.
 * Uses requestAnimationFrame for optimal animation performance and synchronization with the
 * browser's refresh rate.
 *
 * Rendering Process:
 * 1. Schedules the next frame
 * 2. Clears the previous frame
 * 3. Renders each sticker with its current position and rotation
 *
 * Canvas Operations:
 * - clearRect: Clears the entire canvas for the next frame
 * - save: Stores the current canvas state
 * - translate: Moves the origin to the sticker's position
 * - rotate: Applies the sticker's current rotation
 * - drawImage: Renders the sticker image with proper sizing and centering
 * - restore: Restores the canvas to its previous state
 *
 * @function render
 * @private
 *
 * Parameters for drawImage:
 * @param {Image} sticker.img - The sticker image to render
 * @param {number} -StickerSize/2 - X offset for centering
 * @param {number} -StickerSize/2 - Y offset for centering
 * @param {number} corrected_size.width - Width maintaining aspect ratio
 * @param {number} corrected_size.height - Height maintaining aspect ratio
 *
 * State Management:
 * - Position and angle are extracted from the physics body
 * - Canvas state is saved before and restored after each sticker render
 * - Sticker sizes are calculated dynamically based on current count
 *
 * Note: The function uses closure scope to access:
 * - canvas_context: The 2D rendering context
 * - stickers: Array of sticker objects
 * - StickerSize: Current size for sticker scaling
 * - calculateProportionalSize: Helper function for size calculations
 */
(function render() {
    window.requestAnimationFrame(render);

    canvas_context.clearRect(0, 0, canvas.width, canvas.height);

    // for (const sticker of stickers) {
    //     const { position, angle} = sticker.body;
    //     // const { position, angle, bounds} = sticker.body;
    //     // const width = bounds.max.x - bounds.min.x;
    //     // const height = bounds.max.y - bounds.min.y;
    //
    //     canvas_context.save();
    //     canvas_context.translate(position.x, position.y);
    //     canvas_context.rotate(angle);
    //     // drawImage(image, dx, dy, dWidth, dHeight)
    //     const corrected_size = calculateProportionalSize(sticker.img.width, sticker.img.height, StickerSize);
    //     canvas_context.drawImage(sticker.img, -corrected_size.width / 2, -corrected_size.height / 2, corrected_size.width, corrected_size.height);
    //     canvas_context.restore();
    // }

    AnimationManager.updateAnimations(performance.now());

    stickers.forEach(sticker => {
        const { position, angle } = sticker.body;

        canvas_context.save();
        canvas_context.translate(position.x, position.y);
        canvas_context.rotate(angle);

        // Apply scale and alpha if sticker is animating
        const scale = sticker.scale || 1;
        const alpha = sticker.alpha || 1;

        canvas_context.globalAlpha = alpha;
        canvas_context.scale(scale, scale);

        // Get dimensions for centering
        // const width = sticker.body.bounds.max.x - sticker.body.bounds.min.x;
        // const height = sticker.body.bounds.max.y - sticker.body.bounds.min.y;
        //     const corrected_size = calculateProportionalSize(sticker.img.width, sticker.img.height, StickerSize);
        const {width, height} = calculateProportionalSize(sticker.img.width, sticker.img.height, StickerSize);

        canvas_context.drawImage(
            sticker.img,
            -width/2,
            -height/2,
            width,
            height
        );


        // Debug: Show Physics
        if (config.debug.showPhysics) {
            // Reset transform for debug drawing
            canvas_context.restore();
            canvas_context.save();

            // Draw bounding box
            canvas_context.strokeStyle = config.debug.colors.bounds;
            canvas_context.lineWidth = 1;
            canvas_context.beginPath();
            canvas_context.moveTo(sticker.body.bounds.min.x, sticker.body.bounds.min.y);
            canvas_context.lineTo(sticker.body.bounds.max.x, sticker.body.bounds.min.y);
            canvas_context.lineTo(sticker.body.bounds.max.x, sticker.body.bounds.max.y);
            canvas_context.lineTo(sticker.body.bounds.min.x, sticker.body.bounds.max.y);
            canvas_context.closePath();
            canvas_context.stroke();

            // Draw center point
            canvas_context.fillStyle = config.debug.colors.center;
            canvas_context.beginPath();
            canvas_context.arc(position.x, position.y, 3, 0, Math.PI * 2);
            canvas_context.fill();

            // Draw velocity vector
            const velocityScale = 10;
            canvas_context.strokeStyle = '#0000ff';
            canvas_context.beginPath();
            canvas_context.moveTo(position.x, position.y);
            canvas_context.lineTo(
                position.x + sticker.body.velocity.x * velocityScale,
                position.y + sticker.body.velocity.y * velocityScale
            );
            canvas_context.stroke();
        }

        // Debug: Show Sticker Size
        if (config.debug.showStickerSize) {
            canvas_context.font = '12px Arial';
            canvas_context.fillStyle = config.debug.colors.text;
            canvas_context.textAlign = 'center';
            canvas_context.textBaseline = 'top';
            const sizeText = `${Math.round(width)}x${Math.round(height)}`;

            // canvas_context.fillText(
            //     sizeText,
            //     position.x,
            //     // sticker.body.bounds.max.y + 5
            //     width + 5
            // );
            canvas_context.fillText(
                sizeText,
                0,
                // sticker.body.bounds.max.y + 5
                height / 2
            );

            // Show velocity
            const velocity = Math.sqrt(
                sticker.body.velocity.x * sticker.body.velocity.x +
                sticker.body.velocity.y * sticker.body.velocity.y
            ).toFixed(2);

            canvas_context.fillText(
                `v: ${velocity}`,
                // position.x,
                0,
                // sticker.body.bounds.max.y + 20
                (height / 2) + 12
            );
        }

        canvas_context.restore();
    });


    // if (config.debug.showWalls) {
    //     //lines for debug
    //     // canvas_context.beginPath();
    //     let bodies = Composite.allBodies(engine.world);
    //     canvas_context.beginPath();
    //
    //     for (let i = 0; i < bodies.length; i += 1) {
    //         canvas_context.save();
    //
    //         // if (!bodies[i].isStatic) {
    //         //     // console.log("Non body");
    //         //     return;
    //         // }
    //         let vertices = bodies[i].vertices;
    //
    //         canvas_context.moveTo(vertices[0].x, vertices[0].y);
    //
    //         for (let j = 1; j < vertices.length; j += 1) {
    //             canvas_context.lineTo(vertices[j].x, vertices[j].y);
    //         }
    //
    //         canvas_context.lineTo(vertices[0].x, vertices[0].y);
    //     }
    //     canvas_context.restore();
    //
    //     canvas_context.lineWidth = 3;
    //     canvas_context.strokeStyle = config.debug.colors.bounds;
    //     canvas_context.stroke();
    // }

    if (config.debug.showWalls) {
        let bodies = Composite.allBodies(engine.world);

        // Draw walls
        canvas_context.beginPath();
        for (let i = 0; i < bodies.length; i += 1) {
            let body = bodies[i];

            // Skip if it's not a wall (static body)
            if (!body.isStatic && !config.debug.showBounds) continue;

            canvas_context.save();
            canvas_context.beginPath();

            let vertices = body.vertices;
            canvas_context.moveTo(vertices[0].x, vertices[0].y);

            for (let j = 1; j < vertices.length; j += 1) {
                canvas_context.lineTo(vertices[j].x, vertices[j].y);
            }

            canvas_context.closePath();

            // Different colors for different wall types
            switch (body.label) {
                case 'centerBlock':
                    canvas_context.strokeStyle = config.debug.colors.centerWall || '#ff00ff';
                    canvas_context.fillStyle = config.debug.colors.centerWall + '40' || '#ff00ff40';
                    break;
                case 'groundBottom':
                case 'groundTop':
                case 'groundLeft':
                case 'groundRight':
                    canvas_context.strokeStyle = config.debug.colors.walls;
                    canvas_context.fillStyle = config.debug.colors.walls + '40'; // 40 is hex for 25% opacity
                    break;
                default:
                    canvas_context.strokeStyle = config.debug.colors.bounds;
                    canvas_context.fillStyle = config.debug.colors.bounds + '40';
                    // canvas_context.fillStyle = 100%;
            }

            canvas_context.lineWidth = 3;
            canvas_context.stroke();
            canvas_context.fill();

            // Add labels if debug text is enabled
            if (config.debug.showLabels) {
                canvas_context.fillStyle = config.debug.colors.text;
                canvas_context.font = '18px Arial';
                canvas_context.textAlign = 'center';
                canvas_context.textBaseline = 'middle';
                canvas_context.fillText(
                    (body.isStatic ? body.label : body.id),
                    body.position.x,
                    body.position.y
                );
            }

            canvas_context.restore();
        }
    }

    // Optionally render mouse constraint
    if (config.debug.showPhysics && mouseConstraint.constraint.bodyB) {
        const pos = mouseConstraint.constraint.bodyB.position;
        const offset = mouseConstraint.constraint.pointB;
        const mousePos = mouseConstraint.mouse.position;

        canvas_context.beginPath();
        canvas_context.moveTo(pos.x + offset.x, pos.y + offset.y);
        canvas_context.lineTo(mousePos.x, mousePos.y);
        canvas_context.strokeStyle = config.debug.colors.physics;
        canvas_context.stroke();
    }


})();
// -----------------------------------------------------------------------------


// Turn off gravity - as a starting point
// engine.world.gravity.y = 0.0;
// engine.world.gravity.x = 0.0;
resetGravity();
// Setup the interval to change gravity every x seconds
// setInterval(applyRandomGravity, 25000);




// For this to work:
// 1. Create a runner
// 2. Run the engine with the runner
// 3. let the Render function to handle the "render" part
// create runner
var runner = Runner.create();
// run the engine
Runner.run(runner, engine);
// renderScreen();

if (config.mouse.enable) {
    initializeMouseInteraction();
}


// // Let's connect
// new WebSocketClient();




// Events.on(engine, 'afterUpdate', () => {
//     const allBodies = Composite.allBodies(engine.world);
//     const speed = 1; // Desired constant speed
//
//     allBodies.forEach(body => {
//         // Skip static bodies
//         if (body.isStatic) return;
//
//         const velocity = body.velocity;
//         // console.log("Setting velocity: ", velocity);
//
//         const currentSpeed = Math.sqrt(velocity.x * velocity.x + velocity.y * velocity.y);
//
//         // if (currentSpeed !== 0) {
//         //     console.log("Current speed: ", currentSpeed);
//         //     Matter.Body.setVelocity(body, {
//         //         x: (velocity.x / currentSpeed) * speed,
//         //         y: (velocity.y / currentSpeed) * speed
//         //     });
//         // } else {
//         //     console.log("Current speed: ", currentSpeed);
//         //
//         //     // Optional: Give static objects an initial push
//         //     Matter.Body.setVelocity(body, {
//         //         x: (Math.random() - 0.5) * speed,
//         //         y: (Math.random() - 0.5) * speed
//         //     });
//         // }
//         // console.log("Setting speed: ", currentSpeed);
//
//         if (velocity.x >= -0.1 && velocity.x <= 0.1) {
//             Matter.Body.setVelocity(body, {
//                 x: getRandomVelocity(),
//                 // y: Math.random()
//                 y: velocity.y
//             });
//             console.log("Function X", "X Velocity: ", velocity.x, " Y Velocity: ", velocity.y);
//
//         }
//         if (velocity.y >= -0.1 && velocity.y <= 0.1) {
//             Matter.Body.setVelocity(body, {
//                 // x: Math.random(),
//                 x: velocity.x,
//                 y: getRandomVelocity()
//             });
//             console.log("Function Y", "X Velocity: ", velocity.x, " Y Velocity: ", velocity.y);
//         }
//     });
//
// });

// -----------------------------------------------------------------------------
// Collision handling
Events.on(engine, 'collisionStart', (event) => {
    if (!config.world.walls.colisionEffectEnable) {
        return;
    }

    event.pairs.forEach((pair) => {
        const bodyA = pair.bodyA;
        const bodyB = pair.bodyB;

        // Check if one of the bodies is a wall (static)
        if (bodyA.isStatic || bodyB.isStatic) {
            const movingBody = bodyA.isStatic ? bodyB : bodyA;

            // Generate new random angle and maintain constant speed
            const speed = randomIntFromInterval(1,2);
            const randomAngle = Math.random() * Math.PI * 2;

            // Apply new velocity in random direction but maintain speed
            Matter.Body.setVelocity(movingBody, {
                x: Math.cos(randomAngle) * speed,
                y: Math.sin(randomAngle) * speed
            });
        }
    });
});

// -----------------------------------------------------------------------------
// // Optional: Maintain constant speed for all bodies
// Events.on(engine, 'afterUpdate', () => {
//     const allBodies = Composite.allBodies(engine.world);
//     const desiredSpeed = 2;
//
//     allBodies.forEach(body => {
//         if (!body.isStatic) {
//             const velocity = body.velocity;
//             const currentSpeed = Math.sqrt(velocity.x * velocity.x + velocity.y * velocity.y);
//
//             if (currentSpeed !== 0) {
//                 Matter.Body.setVelocity(body, {
//                     x: (velocity.x / currentSpeed) * desiredSpeed,
//                     y: (velocity.y / currentSpeed) * desiredSpeed
//                 });
//             }
//         }
//     });
// });

// Events.on(engine, 'beforeUpdate', function() {
//     engine.gravity.x = Math.cos(engine.timing.timestamp * 0.0005);
//     engine.gravity.y = Math.sin(engine.timing.timestamp * 0.0005);
// });



document.addEventListener('DOMContentLoaded', () => {
    restoreStickers();

    // Let's connect
    new WebSocketClient();

});

window.addEventListener('keydown', (event) => {
    switch(event.key) {
        case '1':
            config.debug.showPhysics = false;
            config.debug.showWalls = true;
            config.debug.showLabels = true;
            config.debug.showStickerSize = true;
            config.debug.showBounds = true;
            break;
        case '2':
            config.debug.showPhysics = false;
            config.debug.showWalls = false;
            config.debug.showLabels = false;
            config.debug.showStickerSize = false;
            config.debug.showBounds = false;
            break;
        case '3':
            config.debug.showPhysics = !config.debug.showPhysics;
            break;
        case '4':
            config.debug.showStickerSize = !config.debug.showStickerSize;
            break;
        case '5':
            config.debug.showWalls = !config.debug.showWalls;
            break;
        case '6':
            config.debug.showLabels = !config.debug.showLabels;
            break;
        case '7':
            config.debug.showBounds = !config.debug.showBounds;
            break;
    }
});







// Add periodic check for stuck animations
setInterval(() => {
    AnimationManager.checkAllStickers();
}, config.animations.protection.checkInterval);




