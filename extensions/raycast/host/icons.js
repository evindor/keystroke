"use strict";

const path = require("path");
const { state } = require("./environment");

const ICON_NAMES = [
  "AddPerson", "Airplane", "AirplaneFilled", "AirplaneLanding", "AirplaneTakeoff", "Airpods",
  "Alarm", "AlarmRinging", "AlignCentre", "AlignLeft", "AlignRight", "AmericanFootball",
  "Anchor", "AppWindow", "AppWindowGrid2x2", "AppWindowGrid3x3", "AppWindowList",
  "AppWindowSidebarLeft", "AppWindowSidebarRight", "ArrowClockwise", "ArrowCounterClockwise",
  "ArrowDown", "ArrowDownCircle", "ArrowDownCircleFilled", "ArrowLeft", "ArrowLeftCircle",
  "ArrowLeftCircleFilled", "ArrowNe", "ArrowRight", "ArrowRightCircle", "ArrowRightCircleFilled",
  "ArrowUp", "ArrowUpCircle", "ArrowUpCircleFilled", "AtSymbol", "BandAid", "BankNote",
  "BarChart", "BarCode", "BathTub", "Battery", "BatteryCharging", "BatteryDisabled",
  "Bell", "BellDisabled", "Binoculars", "Bird", "Bluetooth", "Boat", "Bold", "Bolt",
  "BoltDisabled", "Book", "Bookmark", "Box", "Brush", "Bubble", "Bug", "Building", "BulletPoints",
  "BullsEye", "Calculator", "Calendar", "Camera", "Car", "Cart", "Cd", "Center", "Check",
  "CheckCircle", "CheckList", "Checkmark", "ChessPiece", "ChevronDown", "ChevronDownSmall",
  "ChevronLeft", "ChevronLeftSmall", "ChevronRight", "ChevronRightSmall", "ChevronUp",
  "ChevronUpSmall", "Circle", "CircleEllipsis", "CircleFilled", "CircleProgress", "CircleProgress100",
  "CircleProgress25", "CircleProgress50", "CircleProgress75", "Clipboard", "Clock", "Cloud",
  "CloudLightning", "CloudRain", "CloudSnow", "CloudSun", "Code", "CodeBlock", "Cog", "Coin",
  "Coins", "CommandSymbol", "Compass", "ComputerChip", "Contrast", "CopyClipboard", "CreditCard",
  "CricketBall", "Crop", "Crown", "Crypto", "DeleteDocument", "Desktop", "Dna", "Document",
  "Dot", "Download", "Duplicate", "EditShape", "Eject", "Ellipsis", "EllipsisVertical", "Emoji",
  "Envelope", "Euro", "ExclamationMark", "Exclamationmark", "Eye", "EyeDisabled", "EyeDropper",
  "EyeSlash", "Female", "FilmStrip", "Filter", "Finder", "Fingerprint", "Flag", "Folder",
  "Footprints", "Forward", "ForwardFilled", "FountainTip", "FullSignal", "GameController",
  "Gauge", "Gear", "Geopin", "Germ", "Gift", "Glasses", "Globe", "Goal", "Hammer", "HardDrive",
  "Hashtag", "Headphones", "Heart", "HeartDisabled", "Heartbeat", "Hourglass", "House", "Image",
  "Important", "Info", "Italics", "Joystick", "Key", "Keyboard", "Layers", "Leaderboard",
  "Leaf", "LevelMeter", "LightBulb", "LightBulbOff", "LineChart", "Link", "List", "Livestream",
  "Lock", "LockDisabled", "LockUnlocked", "Logout", "Lorry", "Lowercase", "MagnifyingGlass",
  "Male", "Map", "Mask", "Maximize", "MedicalSupport", "Megaphone", "MemoryChip", "MemoryStick",
  "Message", "Microphone", "MicrophoneDisabled", "Minimize", "Minus", "MinusCircle", "MinusCircleFilled",
  "Mobile", "Monitor", "Moon", "Mountain", "Mouse", "Multiply", "Music", "Network", "NewDocument",
  "Number00", "Number01", "Number02", "Number03", "Number04", "Number05", "Number06", "Number07",
  "Number08", "Number09", "Number10", "Number11", "Number12", "Number13", "Number14", "Number15",
  "Number16", "Number17", "Number18", "Number19", "Number20", "Number21", "Number22", "Number23",
  "Number24", "Number25", "Number26", "Number27", "Number28", "Number29", "Number30", "Number31",
  "Number32", "Number33", "Number34", "Number35", "Number36", "Number37", "Number38", "Number39",
  "Number40", "Number41", "Number42", "Number43", "Number44", "Number45", "Number46", "Number47",
  "Number48", "Number49", "Number50", "Number51", "Number52", "Number53", "Number54", "Number55",
  "Number56", "Number57", "Number58", "Number59", "Number60", "Number61", "Number62", "Number63",
  "Number64", "Number65", "Number66", "Number67", "Number68", "Number69", "Number70", "Number71",
  "Number72", "Number73", "Number74", "Number75", "Number76", "Number77", "Number78", "Number79",
  "Number80", "Number81", "Number82", "Number83", "Number84", "Number85", "Number86", "Number87",
  "Number88", "Number89", "Number90", "Number91", "Number92", "Number93", "Number94", "Number95",
  "Number96", "Number97", "Number98", "Number99", "Paragraph", "Patch", "Pause", "PauseFilled",
  "Pencil", "Person", "PersonCircle", "PersonLines", "Phone", "PhoneRinging", "PieChart", "Pill",
  "Pin", "PinDisabled", "Play", "PlayFilled", "Plug", "Plus", "PlusCircle", "PlusCircleFilled",
  "PlusMinusDivideMultiply", "PlusSquare", "PlusTopRightSquare", "Power", "Print", "QuestionMark",
  "QuestionMarkCircle", "QuotationMarks", "QuoteBlock", "Racket", "Raindrop", "RaycastLogoNeg",
  "RaycastLogoPos", "Receipt", "Redo", "RemovePerson", "Repeat", "Reply", "Rewind", "RewindFilled",
  "Rocket", "Rosin", "RotateAntiClockwise", "RotateClockwise", "Ruler", "SaveDocument", "Shield",
  "ShortParagraph", "Shuffle", "Sidebar", "Signal0", "Signal1", "Signal2", "Signal3", "Snippets",
  "Snowflake", "SoccerBall", "Speaker", "SpeakerDown", "SpeakerHigh", "SpeakerLow", "SpeakerOff",
  "SpeakerOn", "SpeakerUp", "SpeechBubble", "SpeechBubbleActive", "SpeechBubbleImportant",
  "Star", "StarCircle", "StarDisabled", "Stars", "Stop", "StopFilled", "Stopwatch", "Store",
  "StrikeThrough", "Sun", "Sunrise", "Swatch", "Switch", "Syringe", "Tag", "Temperature", "TennisBall",
  "Terminal", "Text", "TextCursor", "TextInput", "Torch", "Train", "Trash", "Tray", "Tree",
  "Trophy", "TwoPeople", "Umbrella", "Underline", "Undo", "Upload", "Uppercase", "Video",
  "Wallet", "Wand", "Warning", "Weights", "Wifi", "WifiDisabled", "Window", "WrenchScrewdriver",
  "WristWatch", "XMarkCircle", "XMarkCircleFilled", "Xmark",
];

const Icon = new Proxy(
  {},
  {
    get(_target, prop) {
      if (prop === Symbol.toPrimitive) return () => "Icon";
      if (typeof prop === "symbol") return undefined;
      if (prop === "then") return undefined;
      return { builtin: String(prop) };
    },
    ownKeys() {
      return ICON_NAMES;
    },
    getOwnPropertyDescriptor(_target, prop) {
      return { enumerable: true, configurable: true, value: { builtin: String(prop) } };
    },
  }
);

const Color = new Proxy(
  {
    PrimaryText: "#ffffff",
    SecondaryText: "#aaaaaa",
    Red: "#ff6363",
    Orange: "#ff9f0a",
    Yellow: "#ffd60a",
    Green: "#30d158",
    Blue: "#0a84ff",
    Purple: "#bf5af2",
    Magenta: "#ff375f",
  },
  {
    get(target, prop) {
      if (prop in target) return target[prop];
      if (typeof prop === "symbol") return undefined;
      return "#" + String(prop);
    },
  }
);

function ImageLike(value) {
  return value;
}

const Image = {
  Mask: { Circle: "circle", RoundedRectangle: "roundedRectangle" },
  Fallback: {},
};

function resolveIcon(value) {
  if (value == null || value === false) return null;
  if (typeof value === "string") return resolveStringIcon(value);
  if (typeof value === "number") return { text: String(value) };
  if (typeof value !== "object") return { text: String(value) };
  if (value.builtin) return { builtin: value.builtin };
  if (value.file) return { file: value.file };
  if (value.url) return { url: value.url };
  if (value.text) return { text: value.text };
  if (value.source != null) return resolveIcon(value.source);
  if (value.value != null && (value.source == null)) return resolveIcon(value.value);
  return null;
}

function resolveStringIcon(value) {
  if (!value) return null;
  if (value.startsWith("data:")) return { url: value };
  if (/^https?:\/\//i.test(value)) return { url: value };
  if (value.startsWith("file://")) return { file: value.slice("file://".length) };
  const looksPath = value.includes("/") || value.includes("\\") || path.isAbsolute(value);
  if (looksPath || /\.(png|jpg|jpeg|gif|svg|webp|icns|ico)$/i.test(value)) {
    const abs = path.isAbsolute(value) ? value : path.resolve(state.assetsPath || ".", value);
    return { file: abs };
  }
  if (value.length <= 4 && /\p{Extended_Pictographic}/u.test(value)) return { text: value };
  return { builtin: value };
}

function accessoryText(accessory) {
  if (accessory == null) return "";
  if (typeof accessory === "string" || typeof accessory === "number") return String(accessory);
  if (accessory.text != null) return String(accessory.text);
  if (accessory.date instanceof Date) return accessory.date.toISOString();
  if (accessory.tag) {
    const tag = accessory.tag;
    return typeof tag === "string" ? tag : tag.value || tag.text || "";
  }
  if (accessory.icon) {
    const icon = resolveIcon(accessory.icon);
    if (icon && icon.builtin) return icon.builtin;
    if (icon && icon.text) return icon.text;
  }
  if (accessory.tooltip) return String(accessory.tooltip);
  return "";
}

module.exports = { Icon, Color, Image, ImageLike, resolveIcon, accessoryText, ICON_NAMES };
