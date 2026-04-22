from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_socketio import SocketIO, emit
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

app = Flask(__name__)
# 初始化实时通信（通话来电通知用）
socketio = SocketIO(app, cors_allowed_origins="*")
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'skillmarket-threementogether-2026')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///skillmarket.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = '请先登录'

# ══════════════════════════════════════════
# 数据模型
# ══════════════════════════════════════════

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='user')
    avatar = db.Column(db.String(200), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    orders = db.relationship('Order', foreign_keys='Order.user_id', backref='buyer', lazy=True)
    reviews = db.relationship('Review', backref='reviewer', lazy=True)

class Provider(db.Model):
    __tablename__ = 'providers'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True)
    name = db.Column(db.String(100))
    bio = db.Column(db.Text, default='')
    skills = db.Column(db.Text, default='')
    rating = db.Column(db.Float, default=5.0)
    location = db.Column(db.String(100), default='')
    user = db.relationship('User', backref=db.backref('provider_profile', uselist=False))
    services = db.relationship('Service', backref='provider', lazy=True)

class Service(db.Model):
    __tablename__ = 'services'
    id = db.Column(db.Integer, primary_key=True)
    provider_id = db.Column(db.Integer, db.ForeignKey('providers.id'))
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price_type = db.Column(db.String(20), default='fixed')
    price = db.Column(db.Float, nullable=False)
    price_min = db.Column(db.Float, default=0)
    price_max = db.Column(db.Float, default=0)
    delivery_time = db.Column(db.String(100), default='')
    service_steps = db.Column(db.Text, default='')
    category = db.Column(db.String(50), nullable=False)
    rating = db.Column(db.Float, default=5.0)
    review_count = db.Column(db.Integer, default=0)
    order_count = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    orders = db.relationship('Order', backref='service', lazy=True)

class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    service_id = db.Column(db.Integer, db.ForeignKey('services.id'))
    provider_id = db.Column(db.Integer, db.ForeignKey('providers.id'))
    status = db.Column(db.String(20), default='pending')
    current_step = db.Column(db.Integer, default=0)
    price = db.Column(db.Float)
    hours = db.Column(db.Float, default=1)
    note = db.Column(db.Text, default='')
    # ── 新增：交付物字段 ──────────────────────────────────
    deliver_note = db.Column(db.Text, default='')   # 卖家填写的交付说明
    deliver_link = db.Column(db.String(500), default='')  # 交付链接（可选）
    delivered_at = db.Column(db.DateTime, nullable=True)  # 交付时间
    # ─────────────────────────────────────────────────────
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    payment = db.relationship('Payment', backref='order', uselist=False)
    review = db.relationship('Review', backref='order', uselist=False)
    provider_rel = db.relationship('Provider', backref='orders')

class Payment(db.Model):
    __tablename__ = 'payments'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), unique=True)
    amount = db.Column(db.Float)
    payment_method = db.Column(db.String(50), default='online')
    payment_status = db.Column(db.String(20), default='paid')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Review(db.Model):
    __tablename__ = 'reviews'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), unique=True)
    service_id = db.Column(db.Integer, db.ForeignKey('services.id'), nullable=True)  # ── 新增：关联服务
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    provider_id = db.Column(db.Integer, db.ForeignKey('providers.id'))
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, default='')
    tags = db.Column(db.String(200), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Message(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    content = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    sender   = db.relationship('User', foreign_keys=[sender_id],   backref='sent_messages')
    receiver = db.relationship('User', foreign_keys=[receiver_id], backref='received_messages')

class Report(db.Model):
    __tablename__ = 'reports'
    id = db.Column(db.Integer, primary_key=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    target_type = db.Column(db.String(20), nullable=False)
    target_id   = db.Column(db.Integer, nullable=False)
    reason  = db.Column(db.String(100), nullable=False)
    detail  = db.Column(db.Text, default='')
    status  = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reporter = db.relationship('User', backref='reports')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ══════════════════════════════════════════
# 常量
# ══════════════════════════════════════════

CATEGORIES = ['设计', '编程', '摄影', '语言', '音乐', '教育', '营销', '写作', '视频', '其他']
CAT_ICONS  = {'设计':'🎨','编程':'💻','摄影':'📸','语言':'🌐','音乐':'🎵',
              '教育':'📚','营销':'📢','写作':'✍️','视频':'🎬','其他':'⭐'}

REPORT_REASONS = [
    '虚假宣传 / 服务与描述严重不符',
    '诈骗 / 收款后拒绝提供服务',
    '骚扰或人身攻击',
    '低质量交付 / 无故拒绝服务',
    '违法违规内容',
    '盗用他人作品',
    '其他原因',
]

# ══════════════════════════════════════════
# 路由
# ══════════════════════════════════════════

@app.route('/')
def index():
    featured  = Service.query.filter_by(is_active=True).order_by(Service.order_count.desc()).limit(8).all()
    newest    = Service.query.filter_by(is_active=True).order_by(Service.created_at.desc()).limit(8).all()
    top_rated = Service.query.filter_by(is_active=True).order_by(Service.rating.desc()).limit(4).all()
    stats = {
        'services':  Service.query.filter_by(is_active=True).count(),
        'providers': Provider.query.count(),
        'orders':    Order.query.filter_by(status='completed').count(),
    }
    return render_template('index.html', featured=featured, newest=newest,
                           top_rated=top_rated, categories=CATEGORIES,
                           cat_icons=CAT_ICONS, stats=stats)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        email    = request.form.get('email','').strip()
        password = request.form.get('password','')
        role     = request.form.get('role','user')
        if not username or not email or not password:
            flash('请填写所有必填字段', 'error'); return redirect(url_for('register'))
        if len(password) < 6:
            flash('密码至少需要6位', 'error'); return redirect(url_for('register'))
        if User.query.filter_by(username=username).first():
            flash('用户名已存在', 'error'); return redirect(url_for('register'))
        if User.query.filter_by(email=email).first():
            flash('该邮箱已被注册', 'error'); return redirect(url_for('register'))
        user = User(username=username, email=email,
                    password=generate_password_hash(password), role=role)
        db.session.add(user); db.session.flush()
        if role == 'provider':
            name = request.form.get('name', username).strip() or username
            p = Provider(user_id=user.id, name=name,
                         bio=request.form.get('bio',''),
                         location=request.form.get('location',''))
            db.session.add(p)
        db.session.commit()
        login_user(user)
        flash(f'注册成功！欢迎加入 SkillMarket，{username} 🎉', 'success')
        return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        email    = request.form.get('email','').strip()
        password = request.form.get('password','')
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash(f'欢迎回来，{user.username}！', 'success')
            return redirect(request.args.get('next') or url_for('index'))
        flash('邮箱或密码错误', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('已安全退出', 'info')
    return redirect(url_for('index'))

@app.route('/services')
def services():
    page     = request.args.get('page', 1, type=int)
    category = request.args.get('category','')
    sort     = request.args.get('sort','newest')
    search   = request.args.get('q','').strip()
    min_p    = request.args.get('min_price', type=float)
    max_p    = request.args.get('max_price', type=float)
    q = Service.query.filter_by(is_active=True)
    if category: q = q.filter_by(category=category)
    if search:   q = q.filter(Service.title.contains(search)|Service.description.contains(search))
    if min_p is not None: q = q.filter(Service.price >= min_p)
    if max_p is not None: q = q.filter(Service.price <= max_p)
    if   sort=='price_asc':  q = q.order_by(Service.price.asc())
    elif sort=='price_desc': q = q.order_by(Service.price.desc())
    elif sort=='rating':     q = q.order_by(Service.rating.desc())
    elif sort=='popular':    q = q.order_by(Service.order_count.desc())
    else:                    q = q.order_by(Service.created_at.desc())
    pagination = q.paginate(page=page, per_page=12, error_out=False)
    return render_template('services.html',
        services=pagination.items, pagination=pagination,
        categories=CATEGORIES, cat_icons=CAT_ICONS,
        current_category=category, sort=sort, search=search)

# ── 修复：评价查询改为按 service_id，与 review_count 保持一致 ──────────────
@app.route('/service/<int:sid>')
def service_detail(sid):
    service = Service.query.get_or_404(sid)
    # 按服务 id 查评价，这样数量与 service.review_count 始终匹配
    reviews = Review.query.filter_by(service_id=sid)\
                          .order_by(Review.created_at.desc()).limit(10).all()
    # 旧数据兼容：若 service_id 字段为空（旧评价），回退到 provider 查询
    if not reviews:
        reviews = Review.query.filter_by(provider_id=service.provider_id)\
                              .order_by(Review.created_at.desc()).limit(10).all()
    similar = Service.query.filter_by(category=service.category, is_active=True)\
                           .filter(Service.id != sid).limit(4).all()
    steps = [s.strip() for s in service.service_steps.split('\n') if s.strip()] \
            if service.service_steps else []
    return render_template('service_detail.html',
                           service=service, reviews=reviews,
                           similar=similar, cat_icons=CAT_ICONS, steps=steps)

@app.route('/order/create/<int:sid>', methods=['POST'])
@login_required
def create_order(sid):
    service = Service.query.get_or_404(sid)
    pp = current_user.provider_profile
    if pp and pp.id == service.provider_id:
        flash('不能购买自己的服务', 'error')
        return redirect(url_for('service_detail', sid=sid))
    note  = request.form.get('note','')
    hours = request.form.get('hours', 1, type=float) or 1
    actual_price = service.price * hours if service.price_type == 'hourly' else service.price
    order = Order(user_id=current_user.id, service_id=service.id,
                  provider_id=service.provider_id, price=actual_price,
                  hours=hours, status='pending', note=note)
    db.session.add(order); db.session.commit()
    flash('订单已创建，请完成支付 💳', 'success')
    return redirect(url_for('order_detail', oid=order.id))

@app.route('/order/<int:oid>')
@login_required
def order_detail(oid):
    order = Order.query.get_or_404(oid)
    pp = current_user.provider_profile
    is_provider = pp and pp.id == order.provider_id
    if order.user_id != current_user.id and not is_provider and current_user.role != 'admin':
        flash('无权查看此订单', 'error')
        return redirect(url_for('my_orders'))
    steps = []
    if order.service and order.service.service_steps:
        steps = [s.strip() for s in order.service.service_steps.split('\n') if s.strip()]
    chat_target = None
    if is_provider:
        chat_target = order.buyer
    elif order.service and order.service.provider and order.service.provider.user:
        chat_target = order.service.provider.user
    return render_template('order_detail.html', order=order, is_provider=is_provider,
                           steps=steps, chat_target=chat_target,
                           REPORT_REASONS=REPORT_REASONS)

@app.route('/order/<int:oid>/pay', methods=['POST'])
@login_required
def pay_order(oid):
    order = Order.query.get_or_404(oid)
    if order.user_id != current_user.id:
        return jsonify({'ok':False,'msg':'无权操作'}), 403
    if order.status != 'pending':
        return jsonify({'ok':False,'msg':'订单状态不允许支付'})
    order.status = 'paid'; order.updated_at = datetime.utcnow()
    db.session.add(Payment(order_id=order.id, amount=order.price,
                           payment_method='在线支付', payment_status='paid'))
    svc = Service.query.get(order.service_id)
    if svc: svc.order_count += 1
    db.session.commit()
    return jsonify({'ok':True,'msg':'支付成功！'})

@app.route('/order/<int:oid>/start', methods=['POST'])
@login_required
def start_order(oid):
    order = Order.query.get_or_404(oid)
    pp = current_user.provider_profile
    if not pp or pp.id != order.provider_id:
        return jsonify({'ok':False,'msg':'无权操作'}), 403
    if order.status != 'paid':
        return jsonify({'ok':False,'msg':'请等待买家支付'})
    order.status = 'in_progress'; order.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'ok':True,'msg':'已开始服务'})

@app.route('/order/<int:oid>/step', methods=['POST'])
@login_required
def update_step(oid):
    order = Order.query.get_or_404(oid)
    pp = current_user.provider_profile
    if not pp or pp.id != order.provider_id:
        return jsonify({'ok':False,'msg':'无权操作'}), 403
    step = request.form.get('step', type=int)
    if step is not None:
        order.current_step = step; order.updated_at = datetime.utcnow()
        db.session.commit()
    return jsonify({'ok':True,'current_step':order.current_step})

# ── 修复：deliver 接口保存 note 和 link ──────────────────────────────────
@app.route('/order/<int:oid>/deliver', methods=['POST'])
@login_required
def deliver_order(oid):
    order = Order.query.get_or_404(oid)
    pp = current_user.provider_profile
    if not pp or pp.id != order.provider_id:
        return jsonify({'ok':False,'msg':'无权操作'}), 403
    if order.status != 'in_progress':
        return jsonify({'ok':False,'msg':'当前状态不允许交付'})
    deliver_note = request.form.get('note','').strip()
    deliver_link = request.form.get('link','').strip()
    if not deliver_note:
        return jsonify({'ok':False,'msg':'请填写交付说明'})
    order.status       = 'delivered'
    order.deliver_note = deliver_note
    order.deliver_link = deliver_link
    order.delivered_at = datetime.utcnow()
    order.updated_at   = datetime.utcnow()
    db.session.commit()
    return jsonify({'ok':True,'msg':'已提交交付，等待买家验收 📬'})

@app.route('/order/<int:oid>/complete', methods=['POST'])
@login_required
def complete_order(oid):
    order = Order.query.get_or_404(oid)
    is_buyer    = order.user_id == current_user.id
    pp          = current_user.provider_profile
    is_provider = pp and pp.id == order.provider_id
    if not is_buyer and not is_provider and current_user.role != 'admin':
        return jsonify({'ok':False,'msg':'无权操作'}), 403
    order.status = 'completed'; order.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'ok':True,'msg':'订单已完成！感谢使用 SkillMarket 🎉'})

@app.route('/order/<int:oid>/cancel', methods=['POST'])
@login_required
def cancel_order(oid):
    order = Order.query.get_or_404(oid)
    if order.user_id != current_user.id:
        return jsonify({'ok':False,'msg':'无权操作'}), 403
    if order.status not in ('pending','paid'):
        return jsonify({'ok':False,'msg':'服务进行中无法取消，请联系客服'})
    order.status = 'cancelled'; order.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'ok':True,'msg':'订单已取消'})

# ── 修复：评价时同时写入 service_id，保证 service_detail 查询匹配 ────────
@app.route('/order/<int:oid>/review', methods=['POST'])
@login_required
def add_review(oid):
    order = Order.query.get_or_404(oid)
    if order.user_id != current_user.id:
        flash('无权操作', 'error'); return redirect(url_for('my_orders'))
    if order.status != 'completed':
        flash('只能评价已完成的订单', 'error'); return redirect(url_for('order_detail', oid=oid))
    if order.review:
        flash('已评价过此订单', 'error'); return redirect(url_for('order_detail', oid=oid))
    rating  = int(request.form.get('rating', 5))
    comment = request.form.get('comment','')
    tags    = ','.join(request.form.getlist('tags'))
    rev = Review(
        order_id=order.id,
        service_id=order.service_id,   # ← 新增：写入服务 id
        user_id=current_user.id,
        provider_id=order.provider_id,
        rating=rating,
        comment=comment,
        tags=tags
    )
    db.session.add(rev)
    # 重新统计该服务的评分（只算该服务的评价）
    svc = Service.query.get(order.service_id)
    if svc:
        all_revs = Review.query.filter_by(service_id=order.service_id).all() + [rev]
        avg = round(sum(r.rating for r in all_revs) / len(all_revs), 1)
        svc.rating       = avg
        svc.review_count = len(all_revs)   # ← 与 service_detail 查询数量一致
    # 同步更新 provider 总评分
    prov = Provider.query.get(order.provider_id)
    if prov:
        prov_revs = Review.query.filter_by(provider_id=order.provider_id).all() + [rev]
        prov.rating = round(sum(r.rating for r in prov_revs) / len(prov_revs), 1)
    db.session.commit()
    flash('评价已提交，感谢反馈！⭐', 'success')
    return redirect(url_for('order_detail', oid=oid))

@app.route('/my-orders')
@login_required
def my_orders():
    status = request.args.get('status','')
    q = Order.query.filter_by(user_id=current_user.id)
    if status: q = q.filter_by(status=status)
    orders = q.order_by(Order.created_at.desc()).all()
    return render_template('my_orders.html', orders=orders,
                           current_status=status, cat_icons=CAT_ICONS)

@app.route('/profile')
@login_required
def profile():
    total     = Order.query.filter_by(user_id=current_user.id).count()
    completed = Order.query.filter_by(user_id=current_user.id, status='completed').count()
    unread    = Message.query.filter_by(receiver_id=current_user.id, is_read=False).count()
    return render_template('profile.html', orders_count=total,
                           completed_count=completed, unread_count=unread)

@app.route('/profile/edit', methods=['POST'])
@login_required
def edit_profile():
    new_name = request.form.get('username','').strip()
    if new_name and new_name != current_user.username:
        if User.query.filter_by(username=new_name).first():
            flash('用户名已存在', 'error'); return redirect(url_for('profile'))
        current_user.username = new_name
    if current_user.role == 'provider' and current_user.provider_profile:
        p = current_user.provider_profile
        p.name     = request.form.get('name', p.name)
        p.bio      = request.form.get('bio', p.bio)
        p.location = request.form.get('location', p.location)
        p.skills   = request.form.get('skills', p.skills)
    db.session.commit()
    flash('资料已更新', 'success')
    return redirect(url_for('profile'))

# ══ 消息 / 会话 ══════════════════════════════════════════════════════

@app.route('/messages')
@login_required
def messages():
    sent_to   = db.session.query(Message.receiver_id).filter_by(sender_id=current_user.id)
    recv_from = db.session.query(Message.sender_id).filter_by(receiver_id=current_user.id)
    uids = {r[0] for r in sent_to.all()} | {r[0] for r in recv_from.all()}
    contacts = User.query.filter(User.id.in_(uids)).all()
    info = []
    for u in contacts:
        last = Message.query.filter(
            ((Message.sender_id==current_user.id)&(Message.receiver_id==u.id))|
            ((Message.sender_id==u.id)&(Message.receiver_id==current_user.id))
        ).order_by(Message.created_at.desc()).first()
        unread = Message.query.filter_by(sender_id=u.id, receiver_id=current_user.id, is_read=False).count()
        info.append({'user':u,'last_msg':last,'unread':unread})
    info.sort(key=lambda x: x['last_msg'].created_at if x['last_msg'] else datetime.min, reverse=True)
    total_unread = Message.query.filter_by(receiver_id=current_user.id, is_read=False).count()
    return render_template('messages.html', contacts=info, total_unread=total_unread)

# ── 修复：POST 返回消息 id；GET 渲染 conversation.html ─────────────────
@app.route('/messages/<int:uid>', methods=['GET','POST'])
@login_required
def conversation(uid):
    target = User.query.get_or_404(uid)
    if request.method == 'POST':
        content = request.form.get('content','').strip()
        if not content:
            return jsonify({'ok':False,'msg':'消息不能为空'})
        msg = Message(sender_id=current_user.id, receiver_id=uid, content=content)
        db.session.add(msg)
        db.session.commit()
        # ── 关键修复：返回消息 id，前端用来更新 lastId 防止轮询重复 ──
        return jsonify({'ok':True, 'id': msg.id})
    # GET：标记已读，返回页面
    Message.query.filter_by(sender_id=uid, receiver_id=current_user.id, is_read=False)\
                 .update({'is_read':True})
    db.session.commit()
    msgs = Message.query.filter(
        ((Message.sender_id==current_user.id)&(Message.receiver_id==uid))|
        ((Message.sender_id==uid)&(Message.receiver_id==current_user.id))
    ).order_by(Message.created_at.asc()).all()
    return render_template('conversation.html', target=target, messages=msgs)

# ── 修复：轮询接口路径改为 /poll（与前端 conversation.html 一致）──────────
# 原来是 /api/messages/<uid>/new → 现在统一为 /api/messages/<uid>/poll
@app.route('/api/messages/<int:uid>/poll')
@login_required
def api_poll_messages(uid):
    since = request.args.get('since', type=int, default=0)
    msgs  = Message.query.filter(
        Message.sender_id==uid,
        Message.receiver_id==current_user.id,
        Message.id > since
    ).order_by(Message.created_at.asc()).all()
    for m in msgs:
        m.is_read = True
    db.session.commit()
    return jsonify([{
        'id':         m.id,
        'content':    m.content,
        'sender_id':  m.sender_id,
        # ── 返回 UTC ISO 字符串，前端负责转本地时区显示 ──
        'created_at': m.created_at.strftime('%Y-%m-%dT%H:%M:%S')
    } for m in msgs])

# ══ 举报 ══

@app.route('/report', methods=['GET','POST'])
@login_required
def report():
    target_type = request.args.get('type','provider')
    target_id   = request.args.get('id', type=int, default=0)
    if request.method == 'POST':
        target_type = request.form.get('target_type','provider')
        target_id   = request.form.get('target_id', type=int, default=0)
        reason      = request.form.get('reason','')
        detail      = request.form.get('detail','').strip()
        if not reason:
            flash('请选择举报原因', 'error')
            return redirect(request.referrer or url_for('index'))
        existing = Report.query.filter_by(reporter_id=current_user.id,
                                          target_type=target_type, target_id=target_id).first()
        if existing:
            flash('您已举报过该对象，平台正在处理中', 'info')
            return redirect(request.referrer or url_for('index'))
        db.session.add(Report(reporter_id=current_user.id, target_type=target_type,
                              target_id=target_id, reason=reason, detail=detail))
        db.session.commit()
        flash('举报已提交，平台将在3个工作日内处理，感谢您的监督 🙏', 'success')
        return redirect(request.referrer or url_for('index'))
    return render_template('report.html', target_type=target_type,
                           target_id=target_id, REPORT_REASONS=REPORT_REASONS)

# ══ 服务提供者后台 ══

@app.route('/provider/dashboard')
@login_required
def provider_dashboard():
    if current_user.role not in ['provider','admin']:
        flash('无访问权限', 'error'); return redirect(url_for('index'))
    prov = Provider.query.filter_by(user_id=current_user.id).first()
    if not prov:
        flash('请先完善提供者信息', 'error'); return redirect(url_for('profile'))
    svcs   = Service.query.filter_by(provider_id=prov.id).order_by(Service.created_at.desc()).all()
    orders = Order.query.filter_by(provider_id=prov.id).order_by(Order.created_at.desc()).limit(30).all()
    earnings = db.session.query(db.func.sum(Order.price))\
                         .filter_by(provider_id=prov.id, status='completed').scalar() or 0
    stats = {
        'total_services':  len(svcs),
        'total_orders':    Order.query.filter_by(provider_id=prov.id).count(),
        'pending_orders':  Order.query.filter_by(provider_id=prov.id, status='paid').count(),
        'completed_orders':Order.query.filter_by(provider_id=prov.id, status='completed').count(),
        'total_earnings':  earnings,
    }
    return render_template('provider_dashboard.html',
                           provider=prov, services=svcs, orders=orders,
                           stats=stats, categories=CATEGORIES, cat_icons=CAT_ICONS)

@app.route('/provider/service/new', methods=['GET','POST'])
@login_required
def new_service():
    if current_user.role not in ['provider','admin']:
        flash('无访问权限', 'error'); return redirect(url_for('index'))
    prov = Provider.query.filter_by(user_id=current_user.id).first()
    if not prov:
        flash('请先完善提供者信息', 'error'); return redirect(url_for('profile'))
    if request.method == 'POST':
        title      = request.form.get('title','').strip()
        desc       = request.form.get('description','').strip()
        price_type = request.form.get('price_type','fixed')
        price      = request.form.get('price', type=float)
        price_min  = request.form.get('price_min', type=float) or 0
        price_max  = request.form.get('price_max', type=float) or 0
        category   = request.form.get('category','')
        d_time     = request.form.get('delivery_time','').strip()
        s_steps    = request.form.get('service_steps','').strip()
        if not title or not desc or not price or not category:
            flash('请填写所有必填字段', 'error'); return redirect(url_for('new_service'))
        svc = Service(provider_id=prov.id, title=title, description=desc,
                      price_type=price_type, price=price, price_min=price_min,
                      price_max=price_max, category=category,
                      delivery_time=d_time, service_steps=s_steps)
        db.session.add(svc); db.session.commit()
        flash('服务发布成功！🚀', 'success')
        return redirect(url_for('provider_dashboard'))
    return render_template('service_form.html', service=None, categories=CATEGORIES)

@app.route('/provider/service/<int:sid>/edit', methods=['GET','POST'])
@login_required
def edit_service(sid):
    svc  = Service.query.get_or_404(sid)
    prov = Provider.query.filter_by(user_id=current_user.id).first()
    if not prov or svc.provider_id != prov.id:
        flash('无权编辑此服务', 'error'); return redirect(url_for('provider_dashboard'))
    if request.method == 'POST':
        svc.title         = request.form.get('title', svc.title).strip()
        svc.description   = request.form.get('description', svc.description).strip()
        svc.price_type    = request.form.get('price_type', svc.price_type)
        svc.price         = request.form.get('price', svc.price, type=float)
        svc.price_min     = request.form.get('price_min', type=float) or 0
        svc.price_max     = request.form.get('price_max', type=float) or 0
        svc.category      = request.form.get('category', svc.category)
        svc.delivery_time = request.form.get('delivery_time', svc.delivery_time).strip()
        svc.service_steps = request.form.get('service_steps', svc.service_steps).strip()
        svc.is_active     = 'is_active' in request.form
        db.session.commit()
        flash('服务已更新', 'success')
        return redirect(url_for('provider_dashboard'))
    return render_template('service_form.html', service=svc, categories=CATEGORIES)

# ══ 管理面板 ══

@app.route('/admin')
@login_required
def admin_panel():
    if current_user.role != 'admin':
        flash('无访问权限', 'error'); return redirect(url_for('index'))
    revenue = db.session.query(db.func.sum(Order.price)).filter_by(status='completed').scalar() or 0
    stats = {
        'users':     User.query.count(),
        'providers': Provider.query.count(),
        'services':  Service.query.count(),
        'orders':    Order.query.count(),
        'completed': Order.query.filter_by(status='completed').count(),
        'revenue':   revenue,
        'reports':   Report.query.filter_by(status='pending').count(),
    }
    recent_orders   = Order.query.order_by(Order.created_at.desc()).limit(15).all()
    recent_users    = User.query.order_by(User.created_at.desc()).limit(15).all()
    pending_reports = Report.query.filter_by(status='pending').order_by(Report.created_at.desc()).limit(20).all()
    return render_template('admin.html', stats=stats,
                           recent_orders=recent_orders, recent_users=recent_users,
                           pending_reports=pending_reports, cat_icons=CAT_ICONS)

@app.route('/admin/report/<int:rid>/handle', methods=['POST'])
@login_required
def handle_report(rid):
    if current_user.role != 'admin':
        return jsonify({'ok':False,'msg':'无权操作'}), 403
    rep = Report.query.get_or_404(rid)
    rep.status = request.form.get('action','handled')
    db.session.commit()
    return jsonify({'ok':True})

# ══ 静态内容页面 ══

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/team')
def team():
    return render_template('team.html')

@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/help')
def help_center():
    return render_template('help.html')

# ══ 搜索 API ══

@app.route('/api/search')
def api_search():
    q = request.args.get('q','').strip()
    if not q: return jsonify([])
    results = Service.query.filter(
        Service.is_active==True,
        Service.title.contains(q)|Service.category.contains(q)
    ).limit(8).all()
    return jsonify([{'id':s.id,'title':s.title,'price':s.price,
                     'price_type':s.price_type,'category':s.category} for s in results])

# ══════════════════════════════════════════
# 示例数据
# ══════════════════════════════════════════

def seed():
    if User.query.count() > 0:
        return
    admin = User(username='admin', email='admin@skillmarket.com',
                 password=generate_password_hash('admin123'), role='admin')
    db.session.add(admin)
    pdata = [
        ('黎大凡','zhang@example.com','专业UI/UX设计师，5年经验，服务过100+企业客户','设计,UI,Figma','北京'),
        ('尹小恒','li@example.com','全栈工程师，Python/React/Node，交付快质量高','编程,Python,React','上海'),
        ('方短杰','wang@example.com','商业摄影师，擅长产品和人像，后期精修','摄影,修图,视频','广州'),
        ('冯詹皇','chen@example.com','英/日/法三语翻译，10年口译经验','翻译,英语,日语','深圳'),
        ('唐良帅','zhao@example.com','数字营销专家，SEO/SEM/社媒运营全覆盖','营销,SEO,运营','成都'),
    ]
    provs = []
    for name, email, bio, skills, loc in pdata:
        u = User(username=name, email=email,
                 password=generate_password_hash('pass123'), role='provider')
        db.session.add(u); db.session.flush()
        p = Provider(user_id=u.id, name=name, bio=bio, skills=skills, location=loc, rating=4.8)
        db.session.add(p); db.session.flush()
        provs.append(p)
    sdata = [
        (0,'专业UI界面设计','提供高质量UI界面设计，涵盖移动端与PC端，交付Figma源文件及标注文档。',
         'fixed',299,0,0,'3-5个工作日',
         '需求沟通与确认\n草图/线框图设计\n视觉稿设计\n修改与完善\n交付源文件',
         '设计',4.9,22,88),
        (0,'企业Logo品牌设计','为企业/产品打造专属品牌标识，提供多套方案，附带VI规范说明。',
         'fixed',199,0,0,'2-3个工作日',
         '品牌需求沟通\n概念草图设计\n方案提案（3套）\n细化选定方案\n交付矢量源文件',
         '设计',4.8,18,64),
        (0,'商务PPT设计','专业商务演示PPT制作，图文并茂逻辑清晰，72小时内交付。',
         'hourly',80,0,0,'1-3个工作日',
         '内容大纲确认\n页面设计排版\n内容填充完善\n终稿交付',
         '设计',4.7,31,120),
        (1,'Python爬虫定制开发','数据采集定制方案，支持各类复杂网站，数据导出Excel/JSON/数据库。',
         'negotiable',399,200,800,'5-7个工作日',
         '需求分析与评估\n方案设计\n爬虫开发\n测试与调试\n数据交付及说明文档',
         '编程',4.9,15,52),
        (1,'React前端网页开发','响应式网页开发，现代UI框架，SEO优化，代码整洁注释完善。',
         'negotiable',599,300,1500,'7-14个工作日',
         '需求调研\n原型设计确认\n前端开发\n联调测试\n部署上线',
         '编程',4.8,9,38),
        (2,'商业产品拍摄','专业棚拍+外景，后期精修，适用于电商平台和广告投放。',
         'fixed',899,0,0,'1-2个工作日',
         '拍摄需求沟通\n场景搭建\n正式拍摄\n后期精修\n图片交付',
         '摄影',5.0,8,29),
        (3,'英文文档翻译','英↔中专业翻译，支持商务/法律/学术文件，保证专业准确。',
         'hourly',80,0,0,'1个工作日/千字',
         '文档分析评估\n专业翻译\n校对审核\n交付译稿',
         '语言',4.8,27,98),
        (3,'英语口语一对一陪练','每次1小时，发音纠正+情景对话+商务英语，外教级别体验。',
         'hourly',120,0,0,'预约时间',
         '需求评估与课程规划\n正式上课\n课后作业与反馈',
         '语言',4.9,19,73),
        (4,'小红书/抖音账号运营','内容规划+图文制作+数据分析，助力粉丝快速增长。',
         'negotiable',1299,800,3000,'长期合作',
         '账号诊断与定位\n内容策略制定\n内容创作执行\n数据分析报告\n策略持续优化',
         '营销',4.7,6,22),
    ]
    for row in sdata:
        pi,title,desc,pt,price,pmin,pmax,dtime,steps,cat,rat,rcnt,ocnt = row
        svc = Service(provider_id=provs[pi].id, title=title, description=desc,
                      price_type=pt, price=price, price_min=pmin, price_max=pmax,
                      delivery_time=dtime, service_steps=steps,
                      category=cat, rating=rat, review_count=rcnt, order_count=ocnt)
        db.session.add(svc)
    for i in range(1, 4):
        u = User(username=f'用户{i}', email=f'user{i}@example.com',
                 password=generate_password_hash('pass123'), role='user')
        db.session.add(u)
    db.session.commit()
    print('✅ 示例数据初始化完成')

def auto_migrate():
    """
    自动迁移：检测并添加新字段，兼容 SQLite 和 PostgreSQL。
    每次启动时运行，已存在的字段会自动跳过，不影响现有数据。
    """
    db_url = app.config['SQLALCHEMY_DATABASE_URI']
    try:
        if 'postgresql' in db_url or 'postgres' in db_url:
            migrations = [
                "ALTER TABLE orders  ADD COLUMN IF NOT EXISTS deliver_note TEXT DEFAULT ''",
                "ALTER TABLE orders  ADD COLUMN IF NOT EXISTS deliver_link VARCHAR(500) DEFAULT ''",
                "ALTER TABLE orders  ADD COLUMN IF NOT EXISTS delivered_at TIMESTAMP",
                "ALTER TABLE reviews ADD COLUMN IF NOT EXISTS service_id INTEGER",
            ]
            with db.engine.connect() as conn:
                for sql in migrations:
                    try:
                        conn.execute(db.text(sql))
                        conn.commit()
                    except Exception:
                        conn.rollback()
        else:
            import sqlite3
            db_path = db_url.replace('sqlite:///', '')
            if not db_path or db_path == ':memory:':
                return
            con = sqlite3.connect(db_path)
            cur = con.cursor()
            def col_exists(table, col):
                cur.execute(f"PRAGMA table_info({table})")
                return any(r[1] == col for r in cur.fetchall())
            migrations = [
                ('orders',  'deliver_note', "ALTER TABLE orders ADD COLUMN deliver_note TEXT DEFAULT ''"),
                ('orders',  'deliver_link', "ALTER TABLE orders ADD COLUMN deliver_link VARCHAR(500) DEFAULT ''"),
                ('orders',  'delivered_at', 'ALTER TABLE orders ADD COLUMN delivered_at DATETIME'),
                ('reviews', 'service_id',   'ALTER TABLE reviews ADD COLUMN service_id INTEGER'),
            ]
            for table, col, sql in migrations:
                if not col_exists(table, col):
                    cur.execute(sql)
                    print(f'迁移: 添加字段 {table}.{col}')
            con.commit(); cur.close(); con.close()
    except Exception as e:
        print(f'迁移时出错（可忽略）: {e}')

with app.app_context():
    db.create_all()
    auto_migrate()
    seed()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        auto_migrate()
        seed()
    print('\n' + '═'*50)
    print('  🚀  SkillMarket 已启动！')
    print('  🌐  http://127.0.0.1:5000')
    print('  👑  管理员: admin@skillmarket.com / admin123')
    print('  💼  提供者: zhang@example.com / pass123')
    print('  🛍️   用户:  user1@example.com / pass123')
    print('═'*50 + '\n')
    # 仅修改这一行：app.run → socketio.run，其他完全不变
    socketio.run(app, debug=True, port=5000)
# ===================== 音视频通话 实时通知 =====================
# 用户连接绑定
@socketio.on('connect')
def handle_connect():
    if current_user.is_authenticated:
        socketio.server.enter_room(request.sid, f"user_{current_user.id}")

# 发起通话
@socketio.on('call')
def handle_call(data):
    emit('incomingCall', {'type': data['type']}, room=f"user_{data['to']}")

# 拒绝通话
@socketio.on('reject')
def handle_reject(data):
    emit('callRejected', {}, room=f"user_{data['to']}")
