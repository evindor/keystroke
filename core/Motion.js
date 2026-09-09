.pragma library

// Animation tiers for the palette. One table, in milliseconds, so the feel
// can be tuned in one place: Off shows every change at once, Snappy ties
// changes together over a couple of frames, Fluid eases them.
//
//   slide      a menu level entering (results and breadcrumb) after navigate/back
//   selection  the highlight gliding to the newly selected row
//   flashRise  the activated row brightening; the window starts leaving at its peak
//   flashFall  the brightening fading back out
//   window     the palette appearing and leaving (fade, or slide up)
var TIERS = {
  off:    { level: 0, slide: 0,  selection: 0,  flashRise: 0,  flashFall: 0,  window: 0 },
  snappy: { level: 1, slide: 32, selection: 32, flashRise: 12, flashFall: 28, window: 32 },
  fluid:  { level: 2, slide: 90, selection: 90, flashRise: 20, flashFall: 50, window: 90 }
}
var DEFAULT_TIER = "snappy"

function profile(tier) {
  return TIERS[String(tier || "")] || TIERS[DEFAULT_TIER]
}

// How far the card starts below its resting place for the slide-up transition,
// and how far a menu level starts to the side, both before scaling.
var WINDOW_SLIDE_PX = 20
var LEVEL_SLIDE_PX = 28

// Direction of a level change: +1 opens a deeper screen (enters from the
// right), -1 returns to the parent (enters from the left).
function levelOffset(direction, px) {
  var d = Number(direction) || 0
  return d > 0 ? px : d < 0 ? -px : 0
}
