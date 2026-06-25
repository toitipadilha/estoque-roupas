from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, Response
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime, date
import os, csv, io

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'estoque-toiti-2024-mude-em-producao')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///estoque.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ─────────────────────────── MODELS ───────────────────────────

class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    senha_hash = db.Column(db.String(200), nullable=False)
    perfil = db.Column(db.String(20), default='vendedor')
    ativo = db.Column(db.Boolean, default=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    def set_senha(self, s): self.senha_hash = generate_password_hash(s)
    def checar_senha(self, s): return check_password_hash(self.senha_hash, s)


class Categoria(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), unique=True, nullable=False)
    produtos = db.relationship('Produto', backref='categoria', lazy=True)


class Fornecedor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    cnpj = db.Column(db.String(20))
    contato = db.Column(db.String(100))
    telefone = db.Column(db.String(30))
    email = db.Column(db.String(150))
    endereco = db.Column(db.String(255))
    observacao = db.Column(db.Text)
    ativo = db.Column(db.Boolean, default=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    produtos = db.relationship('Produto', backref='fornecedor', lazy=True)
    notas = db.relationship('NotaFiscal', backref='fornecedor', lazy=True)


class Produto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    sku = db.Column(db.String(50), unique=True, nullable=False)
    categoria_id = db.Column(db.Integer, db.ForeignKey('categoria.id'))
    fornecedor_id = db.Column(db.Integer, db.ForeignKey('fornecedor.id'))
    tamanho = db.Column(db.String(20))
    cor = db.Column(db.String(50))
    preco_custo = db.Column(db.Float, default=0)
    preco_venda = db.Column(db.Float, default=0)
    quantidade = db.Column(db.Integer, default=0)
    estoque_minimo = db.Column(db.Integer, default=5)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    movimentacoes = db.relationship('Movimentacao', backref='produto', lazy=True)

    @property
    def status(self):
        if self.quantidade == 0: return 'sem_estoque'
        if self.quantidade <= self.estoque_minimo: return 'baixo'
        return 'ok'


class Movimentacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    produto_id = db.Column(db.Integer, db.ForeignKey('produto.id'), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    observacao = db.Column(db.String(255))
    nota_id = db.Column(db.Integer, db.ForeignKey('nota_fiscal.id'), nullable=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    usuario = db.relationship('Usuario', backref='movimentacoes')
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)


class NotaFiscal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(50), nullable=False)
    serie = db.Column(db.String(10))
    tipo = db.Column(db.String(20), default='entrada')  # entrada / saida
    fornecedor_id = db.Column(db.Integer, db.ForeignKey('fornecedor.id'))
    data_emissao = db.Column(db.Date, default=date.today)
    valor_total = db.Column(db.Float, default=0)
    chave_nfe = db.Column(db.String(50))
    observacao = db.Column(db.Text)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    itens = db.relationship('ItemNota', backref='nota', lazy=True, cascade='all, delete-orphan')
    movimentacoes = db.relationship('Movimentacao', backref='nota', lazy=True)


class ItemNota(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nota_id = db.Column(db.Integer, db.ForeignKey('nota_fiscal.id'), nullable=False)
    produto_id = db.Column(db.Integer, db.ForeignKey('produto.id'), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    preco_unitario = db.Column(db.Float, default=0)
    produto = db.relationship('Produto')


# ─────────────────────────── AUTH ───────────────────────────

def login_required(f):
    @wraps(f)
    def d(*a, **kw):
        if 'usuario_id' not in session: return redirect(url_for('login'))
        return f(*a, **kw)
    return d

def admin_required(f):
    @wraps(f)
    def d(*a, **kw):
        if session.get('perfil') != 'admin':
            flash('Acesso restrito a administradores.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*a, **kw)
    return d

# ─────────────────────────── ROUTES ───────────────────────────

@app.route('/')
def index():
    return redirect(url_for('dashboard') if 'usuario_id' in session else url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'usuario_id' in session: return redirect(url_for('dashboard'))
    if request.method == 'POST':
        u = Usuario.query.filter_by(email=request.form['email'].strip().lower(), ativo=True).first()
        if u and u.checar_senha(request.form['senha']):
            session.update({'usuario_id': u.id, 'nome': u.nome, 'perfil': u.perfil})
            flash(f'Bem-vindo, {u.nome}!', 'success')
            return redirect(url_for('dashboard'))
        flash('E-mail ou senha incorretos.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear(); return redirect(url_for('login'))

# Dashboard
@app.route('/dashboard')
@login_required
def dashboard():
    produtos = Produto.query.all()
    movs = Movimentacao.query.order_by(Movimentacao.criado_em.desc()).limit(8).all()
    alertas = Produto.query.filter(Produto.quantidade <= Produto.estoque_minimo).order_by(Produto.quantidade).limit(8).all()
    return render_template('dashboard.html',
        total_produtos=len(produtos),
        estoque_baixo=sum(1 for p in produtos if p.status == 'baixo'),
        sem_estoque=sum(1 for p in produtos if p.status == 'sem_estoque'),
        total_categorias=Categoria.query.count(),
        valor_estoque=sum(p.quantidade * p.preco_custo for p in produtos),
        valor_venda=sum(p.quantidade * p.preco_venda for p in produtos),
        movimentacoes=movs, alertas=alertas
    )

# ── PRODUTOS ──
@app.route('/produtos')
@login_required
def produtos():
    q = request.args.get('q', '')
    cat = request.args.get('categoria', '')
    status = request.args.get('status', '')
    forn = request.args.get('fornecedor', '')
    query = Produto.query
    if q: query = query.filter(db.or_(Produto.nome.ilike(f'%{q}%'), Produto.sku.ilike(f'%{q}%')))
    if cat: query = query.filter_by(categoria_id=cat)
    if forn: query = query.filter_by(fornecedor_id=forn)
    lista = query.order_by(Produto.nome).all()
    if status == 'baixo': lista = [p for p in lista if p.status == 'baixo']
    elif status == 'sem_estoque': lista = [p for p in lista if p.status == 'sem_estoque']
    return render_template('produtos.html', produtos=lista,
        categorias=Categoria.query.order_by(Categoria.nome).all(),
        fornecedores=Fornecedor.query.filter_by(ativo=True).order_by(Fornecedor.nome).all(),
        q=q, cat_sel=cat, status_sel=status, forn_sel=forn)

@app.route('/produtos/novo', methods=['GET', 'POST'])
@login_required
def produto_novo():
    cats = Categoria.query.order_by(Categoria.nome).all()
    forns = Fornecedor.query.filter_by(ativo=True).order_by(Fornecedor.nome).all()
    if request.method == 'POST':
        sku = request.form['sku'].strip().upper()
        if Produto.query.filter_by(sku=sku).first():
            flash('SKU já cadastrado.', 'danger')
            return render_template('produto_form.html', categorias=cats, fornecedores=forns, produto=None)
        p = Produto(
            nome=request.form['nome'].strip(), sku=sku,
            categoria_id=request.form.get('categoria_id') or None,
            fornecedor_id=request.form.get('fornecedor_id') or None,
            tamanho=request.form.get('tamanho', '').strip(),
            cor=request.form.get('cor', '').strip(),
            preco_custo=float(request.form.get('preco_custo') or 0),
            preco_venda=float(request.form.get('preco_venda') or 0),
            quantidade=int(request.form.get('quantidade') or 0),
            estoque_minimo=int(request.form.get('estoque_minimo') or 5),
        )
        db.session.add(p); db.session.flush()
        if p.quantidade > 0:
            db.session.add(Movimentacao(produto_id=p.id, tipo='entrada', quantidade=p.quantidade,
                                        observacao='Estoque inicial', usuario_id=session['usuario_id']))
        db.session.commit()
        flash('Produto cadastrado!', 'success')
        return redirect(url_for('produtos'))
    return render_template('produto_form.html', categorias=cats, fornecedores=forns, produto=None)

@app.route('/produtos/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def produto_editar(id):
    p = Produto.query.get_or_404(id)
    cats = Categoria.query.order_by(Categoria.nome).all()
    forns = Fornecedor.query.filter_by(ativo=True).order_by(Fornecedor.nome).all()
    if request.method == 'POST':
        p.nome = request.form['nome'].strip()
        p.categoria_id = request.form.get('categoria_id') or None
        p.fornecedor_id = request.form.get('fornecedor_id') or None
        p.tamanho = request.form.get('tamanho', '').strip()
        p.cor = request.form.get('cor', '').strip()
        p.preco_custo = float(request.form.get('preco_custo') or 0)
        p.preco_venda = float(request.form.get('preco_venda') or 0)
        p.estoque_minimo = int(request.form.get('estoque_minimo') or 5)
        db.session.commit()
        flash('Produto atualizado!', 'success')
        return redirect(url_for('produtos'))
    return render_template('produto_form.html', categorias=cats, fornecedores=forns, produto=p)

@app.route('/produtos/<int:id>/excluir', methods=['POST'])
@login_required
@admin_required
def produto_excluir(id):
    p = Produto.query.get_or_404(id)
    Movimentacao.query.filter_by(produto_id=id).delete()
    db.session.delete(p); db.session.commit()
    flash('Produto excluído.', 'success')
    return redirect(url_for('produtos'))

@app.route('/produtos/<int:id>')
@login_required
def produto_detalhe(id):
    p = Produto.query.get_or_404(id)
    movs = Movimentacao.query.filter_by(produto_id=id).order_by(Movimentacao.criado_em.desc()).all()
    return render_template('produto_detalhe.html', produto=p, movimentacoes=movs)

# ── CSV EXPORT ──
@app.route('/produtos/exportar-csv')
@login_required
def exportar_csv():
    produtos = Produto.query.order_by(Produto.nome).all()
    si = io.StringIO()
    w = csv.writer(si, delimiter=';')
    w.writerow(['SKU','Nome','Categoria','Fornecedor','Tamanho','Cor','Quantidade','Estoque Mínimo',
                'Preço Custo','Preço Venda','Valor Estoque (custo)','Valor Estoque (venda)','Status'])
    for p in produtos:
        w.writerow([
            p.sku, p.nome,
            p.categoria.nome if p.categoria else '',
            p.fornecedor.nome if p.fornecedor else '',
            p.tamanho or '', p.cor or '',
            p.quantidade, p.estoque_minimo,
            f'{p.preco_custo:.2f}', f'{p.preco_venda:.2f}',
            f'{p.quantidade * p.preco_custo:.2f}',
            f'{p.quantidade * p.preco_venda:.2f}',
            p.status
        ])
    output = '\ufeff' + si.getvalue()  # BOM para Excel
    return Response(output, mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=estoque_{date.today()}.csv'})

@app.route('/movimentacoes/exportar-csv')
@login_required
def exportar_movimentacoes_csv():
    movs = Movimentacao.query.order_by(Movimentacao.criado_em.desc()).all()
    si = io.StringIO()
    w = csv.writer(si, delimiter=';')
    w.writerow(['Data','Produto','SKU','Tipo','Quantidade','Observação','Usuário','NF'])
    for m in movs:
        w.writerow([
            m.criado_em.strftime('%d/%m/%Y %H:%M'),
            m.produto.nome, m.produto.sku,
            m.tipo, m.quantidade, m.observacao or '',
            m.usuario.nome if m.usuario else '',
            m.nota.numero if m.nota else ''
        ])
    output = '\ufeff' + si.getvalue()
    return Response(output, mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=movimentacoes_{date.today()}.csv'})

# ── MOVIMENTAÇÕES ──
@app.route('/movimentacoes', methods=['GET', 'POST'])
@login_required
def movimentacoes():
    if request.method == 'POST':
        produto_id = request.form['produto_id']
        tipo = request.form['tipo']
        qtd = int(request.form['quantidade'])
        p = Produto.query.get_or_404(produto_id)
        if tipo == 'saida' and qtd > p.quantidade:
            flash('Quantidade maior que o estoque disponível.', 'danger')
        else:
            if tipo == 'entrada': p.quantidade += qtd
            elif tipo == 'saida': p.quantidade -= qtd
            elif tipo == 'ajuste': p.quantidade = qtd
            db.session.add(Movimentacao(produto_id=produto_id, tipo=tipo, quantidade=qtd,
                observacao=request.form.get('observacao', ''), usuario_id=session['usuario_id']))
            db.session.commit()
            flash('Movimentação registrada!', 'success')
        return redirect(url_for('movimentacoes'))
    movs = Movimentacao.query.order_by(Movimentacao.criado_em.desc()).limit(100).all()
    return render_template('movimentacoes.html', movimentacoes=movs,
        produtos=Produto.query.order_by(Produto.nome).all())

# ── FORNECEDORES ──
@app.route('/fornecedores')
@login_required
@admin_required
def fornecedores():
    forns = Fornecedor.query.order_by(Fornecedor.nome).all()
    return render_template('fornecedores.html', fornecedores=forns)

@app.route('/fornecedores/novo', methods=['GET', 'POST'])
@login_required
@admin_required
def fornecedor_novo():
    if request.method == 'POST':
        f = Fornecedor(
            nome=request.form['nome'].strip(),
            cnpj=request.form.get('cnpj', '').strip(),
            contato=request.form.get('contato', '').strip(),
            telefone=request.form.get('telefone', '').strip(),
            email=request.form.get('email', '').strip(),
            endereco=request.form.get('endereco', '').strip(),
            observacao=request.form.get('observacao', '').strip(),
        )
        db.session.add(f); db.session.commit()
        flash('Fornecedor cadastrado!', 'success')
        return redirect(url_for('fornecedores'))
    return render_template('fornecedor_form.html', fornecedor=None)

@app.route('/fornecedores/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def fornecedor_editar(id):
    f = Fornecedor.query.get_or_404(id)
    if request.method == 'POST':
        f.nome = request.form['nome'].strip()
        f.cnpj = request.form.get('cnpj', '').strip()
        f.contato = request.form.get('contato', '').strip()
        f.telefone = request.form.get('telefone', '').strip()
        f.email = request.form.get('email', '').strip()
        f.endereco = request.form.get('endereco', '').strip()
        f.observacao = request.form.get('observacao', '').strip()
        f.ativo = 'ativo' in request.form
        db.session.commit()
        flash('Fornecedor atualizado!', 'success')
        return redirect(url_for('fornecedores'))
    return render_template('fornecedor_form.html', fornecedor=f)

@app.route('/fornecedores/<int:id>/excluir', methods=['POST'])
@login_required
@admin_required
def fornecedor_excluir(id):
    f = Fornecedor.query.get_or_404(id)
    if f.produtos or f.notas:
        flash('Não é possível excluir: há produtos ou notas vinculadas.', 'danger')
    else:
        db.session.delete(f); db.session.commit()
        flash('Fornecedor excluído.', 'success')
    return redirect(url_for('fornecedores'))

# ── NOTAS FISCAIS ──
@app.route('/notas')
@login_required
def notas():
    notas = NotaFiscal.query.order_by(NotaFiscal.data_emissao.desc()).all()
    return render_template('notas.html', notas=notas)

@app.route('/notas/nova', methods=['GET', 'POST'])
@login_required
def nota_nova():
    forns = Fornecedor.query.filter_by(ativo=True).order_by(Fornecedor.nome).all()
    produtos = Produto.query.order_by(Produto.nome).all()
    if request.method == 'POST':
        numero = request.form['numero'].strip()
        tipo = request.form['tipo']
        forn_id = request.form.get('fornecedor_id') or None
        data_str = request.form.get('data_emissao')
        data_em = datetime.strptime(data_str, '%Y-%m-%d').date() if data_str else date.today()
        chave = request.form.get('chave_nfe', '').strip()
        obs = request.form.get('observacao', '').strip()

        # Itens da nota
        prod_ids = request.form.getlist('item_produto[]')
        qtds = request.form.getlist('item_quantidade[]')
        precos = request.form.getlist('item_preco[]')

        if not prod_ids or all(not x for x in prod_ids):
            flash('Adicione ao menos um item à nota.', 'danger')
            return render_template('nota_form.html', fornecedores=forns, produtos=produtos, nota=None)

        valor_total = sum(int(q or 0) * float(p or 0) for q, p in zip(qtds, precos) if q and p)

        nota = NotaFiscal(numero=numero, serie=request.form.get('serie','').strip(),
            tipo=tipo, fornecedor_id=forn_id, data_emissao=data_em,
            valor_total=valor_total, chave_nfe=chave, observacao=obs)
        db.session.add(nota); db.session.flush()

        for pid, qtd_s, preco_s in zip(prod_ids, qtds, precos):
            if not pid or not qtd_s: continue
            qtd = int(qtd_s)
            preco = float(preco_s or 0)
            prod = Produto.query.get(pid)
            if not prod: continue
            db.session.add(ItemNota(nota_id=nota.id, produto_id=int(pid), quantidade=qtd, preco_unitario=preco))
            # Atualiza estoque
            if tipo == 'entrada': prod.quantidade += qtd
            elif tipo == 'saida' and qtd <= prod.quantidade: prod.quantidade -= qtd
            db.session.add(Movimentacao(produto_id=int(pid), tipo=tipo, quantidade=qtd,
                observacao=f'NF {numero}', nota_id=nota.id, usuario_id=session['usuario_id']))

        db.session.commit()
        flash(f'Nota Fiscal {numero} registrada com sucesso!', 'success')
        return redirect(url_for('nota_detalhe', id=nota.id))
    return render_template('nota_form.html', fornecedores=forns, produtos=produtos, nota=None)

@app.route('/notas/<int:id>')
@login_required
def nota_detalhe(id):
    nota = NotaFiscal.query.get_or_404(id)
    return render_template('nota_detalhe.html', nota=nota)

@app.route('/notas/<int:id>/excluir', methods=['POST'])
@login_required
@admin_required
def nota_excluir(id):
    nota = NotaFiscal.query.get_or_404(id)
    # Reverte estoque
    for item in nota.itens:
        p = item.produto
        if nota.tipo == 'entrada': p.quantidade -= item.quantidade
        elif nota.tipo == 'saida': p.quantidade += item.quantidade
    Movimentacao.query.filter_by(nota_id=id).delete()
    db.session.delete(nota); db.session.commit()
    flash('Nota excluída e estoque revertido.', 'success')
    return redirect(url_for('notas'))

# ── CATEGORIAS ──
@app.route('/categorias', methods=['GET', 'POST'])
@login_required
@admin_required
def categorias():
    if request.method == 'POST':
        nome = request.form['nome'].strip()
        if not Categoria.query.filter_by(nome=nome).first():
            db.session.add(Categoria(nome=nome)); db.session.commit()
            flash('Categoria criada!', 'success')
        else:
            flash('Categoria já existe.', 'danger')
        return redirect(url_for('categorias'))
    return render_template('categorias.html', categorias=Categoria.query.order_by(Categoria.nome).all())

@app.route('/categorias/<int:id>/excluir', methods=['POST'])
@login_required
@admin_required
def categoria_excluir(id):
    c = Categoria.query.get_or_404(id)
    if c.produtos: flash('Não é possível excluir: há produtos nessa categoria.', 'danger')
    else:
        db.session.delete(c); db.session.commit()
        flash('Categoria excluída.', 'success')
    return redirect(url_for('categorias'))

# ── USUÁRIOS ──
@app.route('/usuarios')
@login_required
@admin_required
def usuarios():
    return render_template('usuarios.html', usuarios=Usuario.query.order_by(Usuario.nome).all())

@app.route('/usuarios/novo', methods=['GET', 'POST'])
@login_required
@admin_required
def usuario_novo():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        if Usuario.query.filter_by(email=email).first():
            flash('E-mail já cadastrado.', 'danger')
            return render_template('usuario_form.html', usuario=None)
        u = Usuario(nome=request.form['nome'].strip(), email=email, perfil=request.form.get('perfil','vendedor'))
        u.set_senha(request.form['senha']); db.session.add(u); db.session.commit()
        flash('Usuário criado!', 'success'); return redirect(url_for('usuarios'))
    return render_template('usuario_form.html', usuario=None)

@app.route('/usuarios/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def usuario_editar(id):
    u = Usuario.query.get_or_404(id)
    if request.method == 'POST':
        u.nome = request.form['nome'].strip()
        u.perfil = request.form.get('perfil','vendedor')
        u.ativo = 'ativo' in request.form
        if request.form.get('senha','').strip(): u.set_senha(request.form['senha'])
        db.session.commit(); flash('Usuário atualizado!', 'success')
        return redirect(url_for('usuarios'))
    return render_template('usuario_form.html', usuario=u)

# ── RELATÓRIO ──
@app.route('/relatorio')
@login_required
def relatorio():
    produtos = Produto.query.order_by(Produto.nome).all()
    valor_custo = sum(p.quantidade * p.preco_custo for p in produtos)
    valor_venda = sum(p.quantidade * p.preco_venda for p in produtos)
    return render_template('relatorio.html', produtos=produtos,
        valor_custo=valor_custo, valor_venda=valor_venda, margem=valor_venda-valor_custo,
        hoje=date.today().strftime('%d/%m/%Y'))

# ── API produtos (para select dinâmico na NF) ──
@app.route('/api/produto/<int:id>')
@login_required
def api_produto(id):
    p = Produto.query.get_or_404(id)
    return jsonify({'nome': p.nome, 'sku': p.sku, 'preco_custo': p.preco_custo,
                    'preco_venda': p.preco_venda, 'quantidade': p.quantidade})

# ── SEED ──
def seed_db():
    if not Usuario.query.first():
        admin = Usuario(nome='Administrador', email='admin@loja.com', perfil='admin')
        admin.set_senha('admin123'); db.session.add(admin)
        forns_demo = [
            Fornecedor(nome='Moda Brasil Ltda', cnpj='12.345.678/0001-90', contato='Maria',
                       telefone='(35) 99999-0001', email='contato@modabrasil.com'),
            Fornecedor(nome='Tecidos Sul', cnpj='98.765.432/0001-10', contato='João',
                       telefone='(35) 99999-0002', email='vendas@tecidossul.com'),
        ]
        for f in forns_demo: db.session.add(f)
        db.session.flush()
        forn1_id = forns_demo[0].id
        cats = ['Feminino','Masculino','Infantil','Acessórios','Calçados']
        cat_objs = {}
        for c in cats:
            obj = Categoria(nome=c); db.session.add(obj); cat_objs[c] = obj
        db.session.flush()
        demos = [
            ('Camiseta Básica Feminina','CAM-FEM-001','Feminino','P','Branco',25,59.90,30),
            ('Calça Jeans Skinny','CAL-FEM-002','Feminino','38','Azul',80,199.90,12),
            ('Vestido Floral','VES-FEM-003','Feminino','M','Rosa',55,149.90,8),
            ('Camiseta Polo Masculina','CAM-MAS-001','Masculino','G','Preto',40,89.90,15),
            ('Calça Chino','CAL-MAS-002','Masculino','42','Bege',70,179.90,20),
            ('Conjunto Infantil','CON-INF-001','Infantil','4','Azul',30,119.90,5),
            ('Mochila Escolar','MO-INF-002','Infantil','U','Verde',45,139.90,3),
            ('Cinto de Couro','ACE-001','Acessórios','U','Marrom',15,79.90,10),
            ('Tênis Casual','CAL-001','Calçados','38','Branco',160,299.90,4),
        ]
        for nome,sku,cat,tam,cor,custo,venda,qtd in demos:
            p = Produto(nome=nome,sku=sku,categoria_id=cat_objs[cat].id,fornecedor_id=forn1_id,
                        tamanho=tam,cor=cor,preco_custo=custo,preco_venda=venda,quantidade=qtd,estoque_minimo=5)
            db.session.add(p)
        db.session.commit()
        for p in Produto.query.all():
            db.session.add(Movimentacao(produto_id=p.id,tipo='entrada',quantidade=p.quantidade,
                                        observacao='Estoque inicial',usuario_id=1))
        db.session.commit()

if __name__ == '__main__':
    with app.app_context():
        db.create_all(); seed_db()
    app.run(host='0.0.0.0', port=5000, debug=False)
