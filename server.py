import json
import razorpay
from flask import Flask, request, abort, render_template_string, jsonify
import config
from database import channels_col  # Async Motor Collection

app = Flask(__name__)

# Razorpay Client Setup
rzp_client = None
if config.RZP_KEY_ID and config.RZP_KEY_SECRET:
    rzp_client = razorpay.Client(auth=(config.RZP_KEY_ID, config.RZP_KEY_SECRET))


@app.route('/')
def home(): 
    return "Healthy", 200


# ─── 🌟 API ENDPOINT: FETCH LIVE STORIES FROM MONGO (ASYNC) ───
@app.route('/api/get_stories', methods=['GET'])
async def get_stories_api():
    try:
        from main import bot  # Circular import से बचने के लिए
        
        # Bot Username निकालना (Pyrofork Client instance से)
        bot_username = bot.me.username if (hasattr(bot, 'me') and bot.me) else "bot"

        stories_list = []
        
        # Async Motor Cursor से डेटा पढ़ना
        async for item in channels_col.find({}):
            is_combo = item.get('is_combo', False)
            
            story_id = str(item.get('item_id') or item.get('channel_id') or item.get('_id'))
            title = item.get('combo_name') if is_combo else item.get('story_name', item.get('name', 'Premium Show'))
            
            cover = item.get('demo_link') if (item.get('demo_link') and item.get('demo_link').startswith('http')) else 'https://images.unsplash.com/photo-1610890716171-6b1bb98ffd09?q=80&w=600'
            
            stories_list.append({
                "id": story_id,
                "title": title,
                "category": "trending" if (is_combo or item.get('source') == 'pocket') else "new",
                "rating": "4.9",
                "episodes": "Combo Pack" if is_combo else "Full Access Track",
                "tag": "Combo" if is_combo else item.get('source', 'Audio').capitalize(),
                "badge": "✨ SAVINGS" if is_combo else "🔥 VIP PICK",
                "cover": cover,
                "adLink": f"https://t.me/{bot_username}?start={story_id}"
            })
            
        return jsonify({"success": True, "stories": stories_list})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ─── 🌟 MINI APP DYNAMIC HTML ROUTE ───
@app.route('/miniapp')
def miniapp():
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>AC Premium - Cinematic OTT Hub</title>
        <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght=400;500;600;700;800&display=swap');
            body { font-family: 'Plus Jakarta Sans', sans-serif; background-color: #040406; }
            .hide-scrollbar::-webkit-scrollbar { display: none; }
            .premium-glow { box-shadow: 0 0 25px -5px rgba(245, 158, 11, 0.2); }
            .glass-nav { background: rgba(10, 10, 12, 0.7); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); border: 1px solid rgba(255, 255, 255, 0.06); }
            .rank-number { font-size: 8rem; font-weight: 900; line-height: 0.8; -webkit-text-stroke: 2px rgba(255, 255, 255, 0.18); color: transparent; font-style: italic; }
            .fade-slide { transition: all 0.6s cubic-bezier(0.4, 0, 0.2, 1); }
        </style>
    </head>
    <body class="text-gray-200 antialiased selection:bg-amber-500 selection:text-black">

        <div id="splash-screen" class="fixed inset-0 bg-[#040406] z-50 flex flex-col justify-between items-center py-24 text-white transition-opacity duration-500">
            <div></div>
            <div class="flex flex-col items-center space-y-4">
                <div class="w-20 h-20 bg-gradient-to-tr from-amber-500 via-orange-500 to-yellow-400 rounded-3xl flex items-center justify-center shadow-2xl shadow-orange-950/40 border border-amber-400/20">
                    <i class="fa-solid fa-crown text-3xl text-black animate-bounce"></i>
                </div>
                <div class="text-center">
                    <h1 class="text-3xl font-extrabold tracking-widest bg-clip-text text-transparent bg-gradient-to-r from-white via-amber-300 to-orange-500">AC PREMIUM</h1>
                    <p class="text-[10px] uppercase tracking-[0.5em] text-gray-500 font-black mt-1">Unlimited Audio Access</p>
                </div>
            </div>
            <div class="flex flex-col items-center space-y-3">
                <div class="w-6 h-6 border-2 border-t-amber-500 border-neutral-800 rounded-full animate-spin"></div>
                <p class="text-[11px] font-semibold text-gray-400 tracking-wide">Loading Premium Dashboard...</p>
            </div>
        </div>

        <div id="main-app" class="hidden min-h-screen flex flex-col pb-32">
            <header class="bg-[#040406]/90 backdrop-blur-md sticky top-0 z-40 px-5 pt-4 pb-3 flex items-center justify-between border-b border-neutral-900/40">
                <div class="flex items-center space-x-2">
                    <span class="text-2xl font-black tracking-tighter text-white">AC<span class="text-amber-500 font-extrabold text-[10px] ml-1 bg-gradient-to-r from-amber-500/20 to-orange-500/10 px-2 py-0.5 rounded border border-amber-500/30 tracking-wide">PREMIUM</span></span>
                </div>
                <div class="flex items-center space-x-3 text-sm text-gray-400">
                    <div id="global-membership-status" class="text-[10px] bg-neutral-900 text-neutral-400 border border-neutral-800 px-2.5 py-1 rounded-full font-bold">🚫 GUEST</div>
                </div>
            </header>

            <main class="flex-1 px-4 overflow-y-auto mt-2">
                <div id="page-home" class="space-y-7">
                    <div id="hero-slider" class="w-full h-72 rounded-3xl relative overflow-hidden border border-neutral-900 shadow-2xl flex items-end p-5 premium-glow cursor-pointer hidden">
                        <img id="hero-banner-img" class="absolute inset-0 w-full h-full object-cover object-top fade-slide scale-100" src="">
                        <div class="absolute inset-0 bg-gradient-to-t from-[#040406] via-[#040406]/50 to-transparent"></div>
                        <div class="relative z-10 space-y-2 max-w-[95%]">
                            <div class="flex items-center space-x-2">
                                <span class="bg-gradient-to-r from-amber-500 to-orange-600 text-black font-black text-[9px] px-2.5 py-0.5 rounded-md tracking-wider uppercase shadow-md animate-pulse">🔥 TRENDING STAGE</span>
                                <span id="hero-banner-badge" class="text-[10px] font-bold text-amber-400">👑 NO.1</span>
                            </div>
                            <h3 id="hero-banner-title" class="text-3xl font-black leading-none tracking-tight text-white drop-shadow-md">LOADING SHOW</h3>
                            <p id="hero-banner-sub" class="text-xs text-neutral-300 font-medium opacity-90"></p>
                            <div class="flex space-x-1.5 pt-1" id="slider-dots"></div>
                        </div>
                    </div>

                    <div class="flex space-x-2.5 overflow-x-auto hide-scrollbar py-1">
                        <button onclick="filterByTag('All')" class="bg-gradient-to-r from-amber-500 to-orange-500 text-black text-xs font-extrabold px-4 py-2 rounded-full whitespace-nowrap tag-filter-btn shadow-md">All Premium Shows</button>
                        <button onclick="filterByTag('Pocket')" class="bg-neutral-900/80 text-neutral-400 border border-neutral-800 text-xs font-bold px-4 py-2 rounded-full whitespace-nowrap tag-filter-btn transition-all">🎧 Pocket FM</button>
                        <button onclick="filterByTag('Pratilipi')" class="bg-neutral-900/80 text-neutral-400 border border-neutral-800 text-xs font-bold px-4 py-2 rounded-full whitespace-nowrap tag-filter-btn transition-all">🎬 Pratilipi FM</button>
                        <button onclick="filterByTag('Combo')" class="bg-neutral-900/80 text-neutral-400 border border-neutral-800 text-xs font-bold px-4 py-2 rounded-full whitespace-nowrap tag-filter-btn transition-all">🎁 Special Combo</button>
                    </div>

                    <div class="space-y-3">
                        <div class="flex items-center justify-between">
                            <h2 class="text-sm font-extrabold uppercase tracking-widest text-white flex items-center gap-2"><span class="w-1.5 h-4 bg-amber-500 rounded-full shadow-amber-500/50 shadow-md"></span>Top Trending Series</h2>
                        </div>
                        <div class="flex space-x-6 overflow-x-auto hide-scrollbar pb-3 pt-2 pl-2" id="trending-container"></div>
                    </div>

                    <div class="space-y-3">
                        <div class="flex items-center justify-between">
                            <h2 class="text-sm font-extrabold uppercase tracking-widest text-neutral-400 flex items-center gap-2"><span class="w-1.5 h-4 bg-neutral-700 rounded-full"></span>New Updates</h2>
                        </div>
                        <div class="flex space-x-4 overflow-x-auto hide-scrollbar pb-2" id="listings-container"></div>
                    </div>
                </div>

                <div id="page-explore" class="hidden space-y-5">
                    <h2 class="text-xl font-extrabold text-white tracking-tight">Explore VIP Audio</h2>
                    <div class="relative">
                        <input type="text" id="search-bar" placeholder="Search romantic, thriller, action packs..." class="w-full bg-neutral-900/90 text-white pl-12 pr-4 py-4 rounded-2xl text-xs focus:outline-none focus:ring-2 focus:ring-amber-500/40 border border-neutral-800/80 transition-all placeholder:text-neutral-600">
                        <i class="fa-solid fa-magnifying-glass absolute left-4 top-4.5 text-neutral-500 text-sm"></i>
                    </div>
                    <div class="grid grid-cols-2 gap-4" id="explore-grid"></div>
                </div>

                <div id="page-plans" class="hidden space-y-5">
                    <div class="text-center space-y-2 py-2">
                        <h2 class="text-2xl font-black text-transparent bg-clip-text bg-gradient-to-r from-white via-amber-400 to-orange-500">Choose Premium Pass</h2>
                        <p class="text-xs text-neutral-400 max-w-[85%] mx-auto font-medium">Unlock all audio stories, upcoming weekly packs & high-speed streaming server pipeline instantly.</p>
                    </div>
                    
                    <div class="space-y-4">
                        <div onclick="redirectToBotPayment('7_days')" class="bg-gradient-to-r from-neutral-900 to-neutral-950 p-5 rounded-2xl border border-neutral-800 flex justify-between items-center cursor-pointer active:scale-98 transition-all">
                            <div class="space-y-1">
                                <span class="text-[9px] font-black bg-amber-500/10 text-amber-400 border border-amber-500/20 px-2 py-0.5 rounded uppercase">Trial Plan</span>
                                <h3 class="text-lg font-black text-white">7 Days VIP Access</h3>
                                <p class="text-[11px] text-neutral-500 font-medium">Perfect to try premium content flow</p>
                            </div>
                            <div class="text-right">
                                <span class="text-2xl font-black text-amber-500">₹15</span>
                                <p class="text-[9px] text-neutral-500 font-bold uppercase mt-1">Open Bot</p>
                            </div>
                        </div>

                        <div onclick="redirectToBotPayment('15_days')" class="bg-gradient-to-r from-neutral-900 to-neutral-950 p-5 rounded-2xl border border-amber-500/30 flex justify-between items-center cursor-pointer active:scale-98 transition-all ring-1 ring-amber-500/20">
                            <div class="space-y-1">
                                <span class="text-[9px] font-black bg-orange-500/20 text-orange-400 border border-orange-500/20 px-2 py-0.5 rounded uppercase">Superhits Choice</span>
                                <h3 class="text-lg font-black text-white">15 Days Premium Pass</h3>
                                <p class="text-[11px] text-neutral-400 font-medium">Binge-listen complete sagas easily</p>
                            </div>
                            <div class="text-right">
                                <span class="text-2xl font-black text-amber-400">₹25</span>
                                <p class="text-[9px] text-neutral-500 font-bold uppercase mt-1">Open Bot</p>
                            </div>
                        </div>
                    </div>
                </div>

                <div id="page-profile" class="hidden space-y-6">
                    <h2 class="text-xl font-extrabold text-white tracking-tight">Account Ecosystem</h2>
                    <div class="bg-gradient-to-br from-neutral-900 via-neutral-900 to-neutral-950 p-5 rounded-3xl border border-neutral-800/80 flex items-center space-x-4 shadow-xl">
                        <div class="w-16 h-16 rounded-full bg-gradient-to-tr from-amber-500/20 to-orange-500/20 border border-amber-500/30 flex items-center justify-center text-2xl text-amber-500 overflow-hidden">
                            <img id="profile-avatar-large" src="" class="w-full h-full object-cover hidden">
                            <i id="profile-icon-large" class="fa-solid fa-user-astronaut"></i>
                        </div>
                        <div>
                            <h3 id="profile-name" class="text-base font-extrabold text-white">AC Guest User</h3>
                            <p id="profile-id" class="text-[11px] text-neutral-500 font-mono mt-0.5 tracking-wide">ID: ---------</p>
                        </div>
                    </div>
                </div>

                <div id="page-detail" class="hidden space-y-6 pt-1">
                    <button onclick="switchTab('home')" class="text-neutral-400 flex items-center space-x-2 text-xs font-black uppercase tracking-wider bg-neutral-900/50 px-3 py-2 rounded-full border border-neutral-800/40 w-fit active:scale-95 transition-all">
                        <i class="fa-solid fa-arrow-left text-amber-500"></i> <span>Back to Feed</span>
                    </button>
                    <div class="w-full h-96 rounded-3xl relative overflow-hidden border border-neutral-800 shadow-2xl flex items-end p-5">
                        <img id="detail-cover" class="absolute inset-0 w-full h-full object-cover object-center" src="">
                        <div class="absolute inset-0 bg-gradient-to-t from-[#040406] via-[#040406]/50 to-transparent"></div>
                        <div class="relative z-10 space-y-2.5 w-full">
                            <span id="detail-badge" class="bg-amber-500 text-black font-black text-[10px] px-2.5 py-0.5 rounded-md uppercase tracking-wider shadow"></span>
                            <h1 id="detail-title" class="text-3xl font-black text-white leading-none tracking-tight drop-shadow-md"></h1>
                            <div class="flex items-center gap-3 text-xs text-neutral-300 font-bold bg-black/40 backdrop-blur-sm p-2 rounded-xl w-fit border border-white/5">
                                <span class="text-amber-400">⭐ 4.9 Rating</span>
                                <span class="text-neutral-500">•</span>
                                <span id="detail-episodes" class="text-neutral-200"></span>
                            </div>
                        </div>
                    </div>
                    <div id="detail-actions-container" class="pt-3 flex flex-col space-y-3 px-1"></div>
                </div>
            </main>

            <nav class="fixed bottom-5 left-5 right-5 h-18 glass-nav rounded-2xl flex justify-around items-center z-40 px-3 shadow-2xl">
                <button onclick="switchTab('home')" id="nav-home" class="flex flex-col items-center text-amber-500 text-[10px] font-black uppercase tracking-wider gap-1 transition-all"><i class="fa-solid fa-house-chimney text-base"></i><span>Home</span></button>
                <button onclick="switchTab('explore')" id="nav-explore" class="flex flex-col items-center text-neutral-500 text-[10px] font-black uppercase tracking-wider gap-1 transition-all"><i class="fa-solid fa-compass text-base"></i><span>Explore</span></button>
                <button onclick="switchTab('plans')" id="nav-plans" class="flex flex-col items-center text-neutral-500 text-[10px] font-black uppercase tracking-wider gap-1 transition-all"><i class="fa-solid fa-gem text-base"></i><span>VIP Pass</span></button>
                <button onclick="switchTab('profile')" id="nav-profile" class="flex flex-col items-center text-neutral-500 text-[10px] font-black uppercase tracking-wider gap-1 transition-all"><i class="fa-solid fa-user-astronaut text-base"></i><span>Profile</span></button>
            </nav>
        </div>

        <script>
            let storiesData = [];
            let currentUserId = 0;
            let activeSliderIndex = 0;
            let sliderTimer = null;
            let viewStoryId = "";

            const tg = window.Telegram.WebApp;
            tg.ready(); tg.expand();

            window.addEventListener('load', () => {
                setupUserSessionData();
                fetchLiveStories();
            });

            function setupUserSessionData() {
                try {
                    const user = tg.initDataUnsafe?.user;
                    if (user) {
                        currentUserId = Number(user.id);
                        if(user.first_name) {
                            document.getElementById('profile-name').innerText = (user.first_name + " " + (user.last_name || "")).trim();
                        }
                        document.getElementById('profile-id').innerText = "ID: " + user.id;
                        if(user.photo_url) {
                            document.getElementById('profile-avatar-large').src = user.photo_url;
                            document.getElementById('profile-avatar-large').classList.remove('hidden');
                            document.getElementById('profile-icon-large').classList.add('hidden');
                        }
                    }
                } catch (err) { console.log("Session error bound."); }
            }

            function fetchLiveStories() {
                fetch('/api/get_stories')
                    .then(res => res.json())
                    .then(data => {
                        if(data.success) {
                            storiesData = data.stories;
                            const splash = document.getElementById('splash-screen');
                            if(splash) splash.remove();
                            document.getElementById('main-app').classList.remove('hidden');
                            
                            refreshAppDOM();
                            startAutoBannerCarousel();
                        }
                    }).catch(err => alert("Server Sync Error!"));
            }

            function startAutoBannerCarousel() {
                if(sliderTimer) clearInterval(sliderTimer);
                const sliderItems = storiesData.filter(s => s.category === 'trending').slice(0, 6);
                if(sliderItems.length === 0) return;
                
                document.getElementById('hero-slider').classList.remove('hidden');
                const dotContainer = document.getElementById('slider-dots');
                dotContainer.innerHTML = '';
                sliderItems.forEach((_, idx) => {
                    dotContainer.insertAdjacentHTML('beforeend', `<span id="dot-${idx}" class="w-1.5 h-1.5 rounded-full bg-neutral-600 transition-all"></span>`);
                });
                renderActiveSliderFrame(sliderItems[activeSliderIndex]);
                sliderTimer = setInterval(() => {
                    activeSliderIndex = (activeSliderIndex + 1) % sliderItems.length;
                    renderActiveSliderFrame(sliderItems[activeSliderIndex]);
                }, 4000); 
            }

            function renderActiveSliderFrame(story) {
                const imgEl = document.getElementById('hero-banner-img');
                const titleEl = document.getElementById('hero-banner-title');
                const badgeEl = document.getElementById('hero-banner-badge');
                const subEl = document.getElementById('hero-banner-sub');
                imgEl.style.opacity = '0.3';
                setTimeout(() => {
                    imgEl.src = story.cover;
                    titleEl.innerText = story.title;
                    badgeEl.innerText = story.badge || "🔥 VIP PICK";
                    subEl.innerText = `Premium Pack • ${story.episodes}`;
                    imgEl.style.opacity = '1';
                    const sliderItems = storiesData.filter(s => s.category === 'trending').slice(0, 6);
                    sliderItems.forEach((_, idx) => {
                        const dot = document.getElementById(`dot-${idx}`);
                        if(dot) {
                            dot.className = idx === activeSliderIndex ? "w-4 h-1.5 rounded-full bg-amber-500 transition-all duration-300" : "w-1.5 h-1.5 rounded-full bg-neutral-600 transition-all duration-300";
                        }
                    });
                }, 250);
                document.getElementById('hero-slider').onclick = () => openDetails(story.id);
            }

            function refreshAppDOM() {
                renderStoreLayout(storiesData);
            }

            function renderStoreLayout(data) {
                const trend = document.getElementById('trending-container');
                const list = document.getElementById('listings-container');
                const grid = document.getElementById('explore-grid');
                if(!trend || !list || !grid) return;
                trend.innerHTML = ''; list.innerHTML = ''; grid.innerHTML = '';
                
                let tIdx = 1;
                data.forEach(story => {
                    if(story.category === 'trending') {
                        trend.insertAdjacentHTML('beforeend', `
                            <div class="flex items-end relative min-w-[170px] max-w-[170px] h-52 active:scale-95 transition-all duration-200 cursor-pointer pr-3" onclick="openDetails('${story.id}')">
                                <span class="rank-number absolute -left-4 -bottom-6 z-0 select-none">${tIdx}</span>
                                <div class="w-28 h-44 ml-auto relative z-10 rounded-2xl overflow-hidden border border-neutral-800/80 shadow-xl">
                                    <img class="w-full h-full object-cover" src="${story.cover}">
                                    <div class="absolute inset-0 bg-gradient-to-t from-black via-black/20 to-transparent"></div>
                                    <div class="absolute bottom-2 left-2 right-2 text-left">
                                        <h4 class="text-[10px] font-black text-white truncate drop-shadow">${story.title}</h4>
                                    </div>
                                </div>
                            </div>`);
                        tIdx++;
                    } else {
                        list.insertAdjacentHTML('beforeend', `
                            <div class="min-w-[125px] max-w-[125px] bg-neutral-900/30 rounded-2xl p-2 border border-neutral-900 flex flex-col justify-between cursor-pointer active:scale-95 transition-all duration-200" onclick="openDetails('${story.id}')">
                                <img class="w-full h-36 object-cover rounded-xl shadow border border-neutral-800/40" src="${story.cover}">
                                <div class="mt-1.5 text-left px-1">
                                    <h4 class="text-[11px] font-extrabold text-neutral-200 truncate leading-tight">${story.title}</h4>
                                </div>
                            </div>`);
                    }
                    grid.insertAdjacentHTML('beforeend', `
                        <div class="bg-neutral-900/30 p-2.5 rounded-2xl border border-neutral-900 flex flex-col justify-between cursor-pointer active:scale-95 transition-all" onclick="openDetails('${story.id}')">
                            <img class="w-full h-40 object-cover rounded-xl mb-2" src="${story.cover}">
                            <h4 class="text-xs font-bold text-white truncate px-0.5">${story.title}</h4>
                        </div>`);
                });
            }

            function openDetails(id) {
                const story = storiesData.find(s => s.id === id);
                if(!story) return;
                viewStoryId = id;
                document.getElementById('detail-title').innerText = story.title;
                document.getElementById('detail-cover').src = story.cover;
                document.getElementById('detail-badge').innerText = story.badge;
                document.getElementById('detail-episodes').innerText = story.episodes;
                
                const actionsContainer = document.getElementById('detail-actions-container');
                actionsContainer.innerHTML = `
                    <button onclick="triggerBotRedirect('${story.id}')" class="w-full bg-gradient-to-r from-amber-500 via-orange-500 to-amber-600 text-black py-4 rounded-2xl font-black text-xs uppercase tracking-widest shadow-xl flex items-center justify-center space-x-2 active:scale-95 transition-all premium-glow">
                        <i class="fa-solid fa-gem text-sm"></i> <span>Get Pack Access in Bot</span>
                    </button>`;
                
                switchTab('none');
                document.getElementById('page-detail').classList.remove('hidden');
            }

            function triggerBotRedirect(itemId) {
                tg.openTelegramLink("https://t.me/" + tg.initDataUnsafe?.bot_inline_placeholder + "?start=" + itemId);
                tg.close();
            }

            function redirectToBotPayment(planId) {
                tg.openTelegramLink("https://t.me/your_bot_username?start=plan_" + planId);
                tg.close();
            }

            function switchTab(tab) {
                const items = ["home", "explore", "plans", "profile"];
                items.forEach(i => {
                    const p = document.getElementById(`page-${i}`); const n = document.getElementById(`nav-${i}`);
                    if(p) p.classList.add('hidden');
                    if(n) { n.classList.remove('text-amber-500'); n.classList.add('text-neutral-500'); }
                });
                document.getElementById('page-detail').classList.add('hidden');
                if(tab !== 'none') {
                    const targetP = document.getElementById(`page-${tab}`); const targetN = document.getElementById(`nav-${tab}`);
                    if(targetP) targetP.classList.remove('hidden');
                    if(targetN) { targetN.className = "flex flex-col items-center text-amber-500 text-[10px] font-black uppercase tracking-wider gap-1 transition-all"; }
                }
            }
        </script>
    </body>
    </html>
    """
    return render_template_string(html_content)


# ─── 🌟 RAZORPAY WEBHOOK HANDLER (ASYNC) ───
@app.route('/razorpay_webhook', methods=['POST'])
async def razorpay_webhook():
    if not config.RZP_WEBHOOK_SECRET or not rzp_client: 
        abort(400)
        
    webhook_signature = request.headers.get('X-Razorpay-Signature')
    payload = request.data
    try:
        rzp_client.utility.verify_webhook_signature(payload.decode('utf-8'), webhook_signature, config.RZP_WEBHOOK_SECRET)
        data = json.loads(payload)
        
        if data.get('event') == 'payment.captured':
            notes = data['payload']['payment']['entity']['notes']
            
            # Async approve logic invoke karna
            from utils import approve_user_logic
            await approve_user_logic(int(notes['user_id']), int(notes['channel_id']), int(notes['mins']), "Razorpay Online")
    except Exception as e: 
        print(f"[Razorpay Webhook Error]: {e}")
        abort(400)
        
    return 'OK', 200
