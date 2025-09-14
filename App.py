import os
from flask import Flask, request, jsonify, abort, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_migrate import Migrate
from datetime import datetime
from sqlalchemy import CheckConstraint
from sqlalchemy.orm import relationship
import json
from fpdf import FPDF

# ---------------- Config ----------------
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "https://farm2bazaar.vercel.app"}})



# Configure database for Railway MySQL or fallback to SQLite
# 🔑 Update this with your MySQL details
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "QvyappKkUGyrFEhyuHXtTKPnGtOoBxaa")
DB_HOST = os.environ.get("DB_HOST", "trolley.proxy.rlwy.net")          # e.g. containers-us-west-123.railway.app
DB_PORT = os.environ.get("DB_PORT", "38946")               # default MySQL port
DB_NAME = os.environ.get("DB_NAME", "railway")        # your DB name

app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

print(f"SQLALCHEMY_DATABASE_URI: {app.config['SQLALCHEMY_DATABASE_URI']}")

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Generic error handler for 500 Internal Server Error
@app.errorhandler(500)
def internal_server_error(e):
    app.logger.exception('An internal server error occurred: %s', e)
    return jsonify(error="Internal Server Error", message=str(e)), 500

# ---------------- Load Market Data ----------------

# ---------------- Farmer Model ----------------
class Farmer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    farmername = db.Column(db.String(120))
    mobilenumber = db.Column(db.String(15))
    password = db.Column(db.String(128))
    gender = db.Column(db.String(6))
    State = db.Column(db.String(120))
    City = db.Column(db.String(120))
    aadhar = db.Column(db.String(20))

    def to_dict(self):
        return {
            "id": self.id,
            "farmername": self.farmername,
            "mobilenumber": self.mobilenumber,
            "gender": self.gender,
            "State": self.State,
            "City": self.City,
            "aadhar": self.aadhar,
        }

# ---------------- Retailer Model ----------------
class Retailer(db.Model):
    aadhar = db.Column(db.String(20), primary_key=True)
    enterprise_name = db.Column(db.String(130))
    owner_name = db.Column(db.String(120))
    mobilenumber = db.Column(db.String(15))
    password = db.Column(db.String(128))
    State = db.Column(db.String(120))
    City = db.Column(db.String(100))
    Gstin = db.Column(db.String(20))
    Pan = db.Column(db.String(20))

    def to_dict(self):
        return {
            "aadhar": self.aadhar,
            "enterprise_name": self.enterprise_name,
            "owner_name": self.owner_name,
            "mobilenumber": self.mobilenumber,
            "State": self.State,
            "City": self.City,
            "Gstin": self.Gstin,
            "Pan": self.Pan,
        }

# ---------------- Product Model ----------------
class Product(db.Model):
    __tablename__ = "products"
    id = db.Column(db.Integer, primary_key=True)
    farmer_id = db.Column(db.Integer, db.ForeignKey("farmer.id"), nullable=False)

    name = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(80), nullable=False)
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    in_stock = db.Column(db.Boolean, nullable=False, default=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint("price >= 0", name="ck_product_price_nonneg"),
        CheckConstraint("quantity >= 0", name="ck_product_qty_nonneg"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "farmer_id": self.farmer_id,
            "name": self.name,
            "category": self.category,
            "price": self.price,
            "quantity": self.quantity,
            "in_stock": self.in_stock,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

# ---------------- Purchase Model ----------------
class Purchase(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    retailer_id = db.Column(db.String(20), db.ForeignKey("retailer.aadhar"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    payment_type = db.Column(db.String(50), nullable=False)
    payment_amount = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "retailer_id": self.retailer_id,
            "product_id": self.product_id,
            "quantity": self.quantity,
            "payment_type": self.payment_type,
            "payment_amount": self.payment_amount,
            "created_at": self.created_at.isoformat(),
        }

# Farmer has many Products
Farmer.products = relationship("Product", backref="farmer", cascade="all, delete-orphan")
with app.app_context():
    db.create_all()

# ---------------- API Routes ----------------
@app.route('/')
def index():
    return "✅ API is running with MySQL!"

# ---------------- Farmer APIs ----------------
@app.route('/create-farmer', methods=['POST'])
def create_farmer():
    data = request.json
    required_fields = ['farmername', 'mobilenumber', 'password', 'gender', 'State', 'City', 'aadhar']
    if not data or not all(field in data for field in required_fields):
        abort(400, description=f"Must include all fields: {', '.join(required_fields)}")

    farmer = Farmer(**data)
    db.session.add(farmer)
    db.session.commit()
    return jsonify(farmer.to_dict()), 201


@app.route('/login-farmer', methods=['POST'])
def login_farmer():
    data = request.json
    if not data or 'mobilenumber' not in data or 'password' not in data:
        abort(400, description="Must provide mobilenumber and password in JSON body")

    farmer = Farmer.query.filter_by(mobilenumber=data['mobilenumber'], password=data['password']).first()
    if not farmer:
        abort(401, description="Invalid mobilenumber or password")

    return jsonify({
        "success": True,
        "message": "Login successful",
        "farmer": farmer.to_dict()
    }), 200


# ---------------- Retailer APIs ----------------
@app.route('/create-retailer', methods=['POST'])
def create_retailer():
    data = request.json
    required_fields = ['aadhar', 'enterprise_name', 'owner_name', 'mobilenumber', 'password', 'State', 'City', 'Gstin', 'Pan']
    if not data or not all(field in data for field in required_fields):
        abort(400, description=f"Must include all fields: {', '.join(required_fields)}")

    retailer = Retailer(**data)
    db.session.add(retailer)
    db.session.commit()
    return jsonify(retailer.to_dict()), 201


@app.route('/login-retailer', methods=['POST'])
def login_retailer():
    data = request.json
    if not data or 'mobilenumber' not in data or 'password' not in data:
        abort(400, description="Must provide mobilenumber and password in JSON body")

    retailer = Retailer.query.filter_by(mobilenumber=data['mobilenumber'], password=data['password']).first()
    if not retailer:
        abort(401, description="Invalid mobilenumber or password")

    return jsonify({
        "success": True,
        "message": "Login successful",
        "retailer": retailer.to_dict()
    }), 200


# ---------------- Utility ----------------
def require_farmer(farmer_id: int):
    farmer = Farmer.query.get(farmer_id)
    if not farmer:
        abort(404, description="Farmer not found")
    return farmer


# ---------------- Product APIs ----------------
@app.route("/farmers/<int:farmer_id>/products", methods=["POST"])
def create_product(farmer_id):
    require_farmer(farmer_id)
    data = request.get_json() or {}
    required = ["name", "category", "price", "quantity"]
    if not all(k in data for k in required):
        abort(400, description=f"Missing fields: {', '.join(required)}")

    try:
        price = float(data["price"])
        quantity = int(data["quantity"])
    except (TypeError, ValueError):
        abort(400, description="price must be number; quantity must be integer")

    prod = Product(
        farmer_id=farmer_id,
        name=data["name"].strip(),
        category=data["category"].strip(),
        price=price,
        quantity=quantity,
        in_stock=quantity > 0,
    )
    db.session.add(prod)
    db.session.commit()
    return jsonify(prod.to_dict()), 201


@app.route("/farmers/<int:farmer_id>/products", methods=["GET"])
def list_products(farmer_id):
    require_farmer(farmer_id)
    status = request.args.get("status")
    q = Product.query.filter_by(farmer_id=farmer_id)
    if status == "active":
        q = q.filter(Product.in_stock.is_(True), Product.quantity > 0)
    elif status == "soldout":
        q = q.filter(Product.in_stock.is_(False))
    items = [p.to_dict() for p in q.order_by(Product.updated_at.desc()).all()]
    return jsonify(items), 200


@app.route("/farmers/<int:farmer_id>/products/<int:pid>", methods=["PATCH"])
def update_product(farmer_id, pid):
    require_farmer(farmer_id)
    prod = Product.query.filter_by(id=pid, farmer_id=farmer_id).first()
    if not prod:
        abort(404, description="Product not found")

    data = request.get_json() or {}
    if "name" in data:
        prod.name = str(data["name"]).strip()
    if "category" in data:
        prod.category = str(data["category"]).strip()
    if "price" in data:
        try:
            prod.price = float(data["price"])
        except (TypeError, ValueError):
            abort(400, description="price must be number")
    if "quantity" in data:
        try:
            qty = int(data["quantity"])
        except (TypeError, ValueError):
            abort(400, description="quantity must be integer")
        if qty < 0:
            abort(400, description="quantity cannot be negative")
        prod.quantity = qty
        prod.in_stock = qty > 0
    if "in_stock" in data:
        prod.in_stock = bool(data["in_stock"])

    db.session.commit()
    return jsonify(prod.to_dict()), 200


@app.route("/farmers/<int:farmer_id>/products/<int:pid>/soldout", methods=["POST"])
def mark_sold_out(farmer_id, pid):
    require_farmer(farmer_id)
    prod = Product.query.filter_by(id=pid, farmer_id=farmer_id).first()
    if not prod:
        abort(404, description="Product not found")
    prod.in_stock = False
    db.session.commit()
    return jsonify({"success": True, "product": prod.to_dict()}), 200


# ---------------- Retailer Product View ----------------
@app.route("/retailer/<string:retailer_id>/available-products", methods=["GET"])
def get_available_products(retailer_id):
    retailer = Retailer.query.get(retailer_id)
    if not retailer:
        return jsonify({"error": "Retailer not found"}), 404

    products = (
        Product.query.join(Farmer, Product.farmer_id == Farmer.id)
        .filter(Farmer.State == retailer.State, Product.in_stock.is_(True))
        .with_entities(
            Product.id,
            Product.name.label("product_name"),
            Product.category,
            Product.price,
            Product.quantity,
            Farmer.farmername.label("farmer_name"),
        )
        .all()
    )

    response = [
        {
            "id": product.id,  # ✅ Added ID
            "product_name": product.product_name,
            "category": product.category,
            "price": product.price,
            "quantity": product.quantity,
            "farmer_name": product.farmer_name,
        }
        for product in products
    ]

    return jsonify(response), 200


# ---------------- Purchase API ----------------
@app.route("/products/<int:product_id>/purchase", methods=["POST"])
def purchase_product(product_id):
    data = request.json
    retailer_id = data.get("retailer_id")
    quantity = data.get("quantity")
    payment_type = data.get("payment_type")

    # Validate retailer
    retailer = Retailer.query.get(retailer_id)
    if not retailer:
        return jsonify({"error": "Retailer not found"}), 404

    # Validate product
    product = Product.query.get(product_id)
    if not product:
        return jsonify({"error": "Product not found"}), 404

    # Validate quantity
    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid quantity"}), 400

    if quantity <= 0:
        return jsonify({"error": "Quantity must be positive"}), 400

    if product.quantity < quantity:
        return jsonify({"error": "Insufficient stock"}), 400

    # Deduct stock
    product.quantity -= quantity
    product.in_stock = product.quantity > 0
    db.session.commit()

    # ✅ Auto-calc payment amount
    payment_amount = product.price * quantity

    # Record purchase
    purchase = Purchase(
        retailer_id=retailer_id,
        product_id=product_id,
        quantity=quantity,
        payment_type=payment_type,
        payment_amount=payment_amount,
    )
    db.session.add(purchase)
    db.session.commit()

    return jsonify({"success": True, "message": "Purchase successful", "purchase": purchase.to_dict()}), 200


@app.route("/farmers/<int:farmer_id>/product-history", methods=["GET"])
def product_history(farmer_id):
    # Validate farmer
    farmer = Farmer.query.get(farmer_id)
    if not farmer:
        return jsonify({"error": "Farmer not found"}), 404

    # Fetch all products listed by the farmer
    products = Product.query.filter_by(farmer_id=farmer_id).all()

    # Format the response
    response = [
        {
            "product_id": product.id,
            "name": product.name,
            "category": product.category,
            "price": product.price,
            "quantity": product.quantity,
            "in_stock": product.in_stock,
            "listed_date": product.created_at.isoformat(),
            "last_updated": product.updated_at.isoformat() if product.updated_at else None,
        }
        for product in products
    ]

    return jsonify(response), 200


@app.route("/farmers/<int:farmer_id>/transactions", methods=["GET"])
def farmer_transactions(farmer_id):
    # Validate farmer
    farmer = Farmer.query.get(farmer_id)
    if not farmer:
        return jsonify({"error": "Farmer not found"}), 404

    # Fetch all purchases related to the farmer's products
    transactions = (
        db.session.query(Purchase, Product)
        .join(Product, Purchase.product_id == Product.id)
        .filter(Product.farmer_id == farmer_id)
        .all()
    )

    # Format the response
    response = [
        {
            "transaction_id": purchase.id,
            "product_id": product.id,
            "product_name": product.name,
            "category": product.category,
            "quantity_sold": purchase.quantity,
            "payment_type": purchase.payment_type,
            "payment_amount": purchase.payment_amount,
            "sold_date": purchase.created_at.isoformat(),
        }
        for purchase, product in transactions
    ]

    return jsonify(response), 200


# ---------------- Analytics API ----------------
@app.route("/farmers/<int:farmer_id>/analytics", methods=["GET"])
def farmer_analytics(farmer_id):
    # Validate farmer
    farmer = Farmer.query.get(farmer_id)
    if not farmer:
        return jsonify({"error": "Farmer not found"}), 404

    # Fetch all products listed by the farmer
    products = Product.query.filter_by(farmer_id=farmer_id).all()

    # Initialize analytics data
    category_sales = {}
    total_listed_stock = 0
    total_present_stock = 0
    total_revenue = 0

    # Analyze products
    for product in products:
        total_listed_stock += product.quantity + sum(
            purchase.quantity for purchase in Purchase.query.filter_by(product_id=product.id).all()
        )
        total_present_stock += product.quantity

        # Fetch all purchases for the product
        purchases = Purchase.query.filter_by(product_id=product.id).all()
        for purchase in purchases:
            total_revenue += purchase.payment_amount
            if product.category not in category_sales:
                category_sales[product.category] = 0
            category_sales[product.category] += purchase.quantity

    # Determine the most sold category
    most_sold_category = max(category_sales, key=category_sales.get) if category_sales else None

    # Format the response
    response = {
        "total_listed_stock": total_listed_stock,
        "total_present_stock": total_present_stock,
        "total_revenue": total_revenue,
        "most_sold_category": most_sold_category,
        "category_sales": category_sales,
    }

    return jsonify(response), 200


# ---------------- Report API ----------------
@app.route("/farmers/<int:farmer_id>/transactions/report", methods=["GET"])
def generate_transaction_report(farmer_id):
    # Validate farmer
    farmer = Farmer.query.get(farmer_id)
    if not farmer:
        return jsonify({"error": "Farmer not found"}), 404

    # Get query parameters
    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")

    # Debugging logs
    print(f"Generating report for farmer_id: {farmer_id}")
    print(f"From Date: {from_date}, To Date: {to_date}")

    # Validate dates
    if not from_date or not to_date:
        return jsonify({"error": "Both from_date and to_date are required."}), 400

    try:
        from_date = datetime.strptime(from_date, "%Y-%m-%d")
        to_date = datetime.strptime(to_date, "%Y-%m-%d")
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400

    if from_date > to_date:
        return jsonify({"error": "from_date cannot be later than to_date."}), 400

    # Fetch transactions within the date range
    transactions_query = (
        db.session.query(Purchase, Product)
        .join(Product, Purchase.product_id == Product.id)
        .filter(Product.farmer_id == farmer_id)
        .filter(Purchase.created_at >= from_date, Purchase.created_at <= to_date)
    )

    transactions = transactions_query.all()

    # If no transactions found
    if not transactions:
        return jsonify({"error": "No transactions found for the given period."}), 404

    # Generate PDF report
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    # Add title
    pdf.set_font("Arial", style="B", size=16)
    pdf.cell(200, 10, txt=f"Transaction Report for {farmer.farmername}", ln=True, align="C")
    pdf.ln(10)

    # Add date range
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=f"From: {from_date.strftime('%Y-%m-%d')} To: {to_date.strftime('%Y-%m-%d')}", ln=True)
    pdf.ln(10)

    # Add table headers
    pdf.set_font("Arial", style="B", size=12)
    pdf.cell(40, 10, "Transaction ID", border=1)
    pdf.cell(40, 10, "Product Name", border=1)
    pdf.cell(30, 10, "Category", border=1)
    pdf.cell(30, 10, "Quantity", border=1)
    pdf.cell(30, 10, "Amount", border=1)
    pdf.cell(30, 10, "Date", border=1)
    pdf.ln()

    # Add transaction data
    pdf.set_font("Arial", size=12)
    for purchase, product in transactions:
        pdf.cell(40, 10, str(purchase.id), border=1)
        pdf.cell(40, 10, product.name, border=1)
        pdf.cell(30, 10, product.category, border=1)
        pdf.cell(30, 10, str(purchase.quantity), border=1)
        pdf.cell(30, 10, f"₹{purchase.payment_amount:.2f}", border=1)
        pdf.cell(30, 10, purchase.created_at.strftime("%Y-%m-%d"), border=1)
        pdf.ln()

    # Output PDF as a response
    response = make_response(pdf.output(dest="S").encode("latin1"))
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f"attachment; filename=Transaction_Report_{farmer_id}.pdf"
    return response


@app.route("/retailers/<string:retailer_id>/transaction-history", methods=["GET"])
def retailer_transaction_history(retailer_id):
    # Validate retailer
    retailer = Retailer.query.get(retailer_id)
    if not retailer:
        return jsonify({"error": "Retailer not found"}), 404

    # Fetch all purchases made by the retailer
    transactions = (
        db.session.query(Purchase, Product, Farmer)
        .join(Product, Purchase.product_id == Product.id)
        .join(Farmer, Product.farmer_id == Farmer.id)
        .filter(Purchase.retailer_id == retailer_id)
        .all()
    )

    # If no transactions found
    if not transactions:
        return jsonify({"error": "No transactions found for this retailer."}), 404

    # Format the response
    response = [
        {
            "order_id": purchase.id,
            "product_name": product.name,
            "category": product.category,
            "farmer_name": farmer.farmername,
            "quantity": purchase.quantity,
            "payment_type": purchase.payment_type,
            "payment_amount": purchase.payment_amount,
            "purchase_date": purchase.created_at.strftime("%Y-%m-%d"),
        }
        for purchase, product, farmer in transactions
    ]

    return jsonify(response), 200


@app.route("/retailers/<string:retailer_id>/stock-bought-this-month", methods=["GET"])
def stock_bought_this_month(retailer_id):
    # Validate retailer
    retailer = Retailer.query.get(retailer_id)
    if not retailer:
        return jsonify({"error": "Retailer not found"}), 404

    # Get the current month and year
    now = datetime.utcnow()
    current_month = now.month
    current_year = now.year

    # Fetch purchases made by the retailer in the current month
    transactions = (
        db.session.query(Purchase, Product, Farmer)
        .join(Product, Purchase.product_id == Product.id)
        .join(Farmer, Product.farmer_id == Farmer.id)
        .filter(Purchase.retailer_id == retailer_id)
        .filter(db.extract("month", Purchase.created_at) == current_month)
        .filter(db.extract("year", Purchase.created_at) == current_year)
        .all()
    )

    # If no transactions found
    if not transactions:
        return jsonify({"error": "No stock bought this month."}), 404

    # Format the response
    response = [
        {
            "order_id": purchase.id,
            "product_name": product.name,
            "category": product.category,
            "farmer_name": farmer.farmername,
            "quantity": purchase.quantity,
            "payment_type": purchase.payment_type,
            "payment_amount": purchase.payment_amount,
            "purchase_date": purchase.created_at.strftime("%Y-%m-%d"),
        }
        for purchase, product, farmer in transactions
    ]

    return jsonify(response), 200


# ---------------- Product Profit Analysis API ----------------
@app.route("/farmers/<int:farmer_id>/product-profit-analysis", methods=["GET"])
def product_profit_analysis(farmer_id):
    # Validate farmer
    farmer = Farmer.query.get(farmer_id)
    if not farmer:
        return jsonify({"error": "Farmer not found"}), 404

    # Get query parameters
    category = request.args.get("category")
    product_name = request.args.get("product_name")

    # Validate query parameters
    if not category or not product_name:
        return jsonify({"error": "Both category and product_name are required."}), 400

    # Fetch the product's market rate from the market data
    state = farmer.State
    try:
        market_rate = market_data[state]["products"][category][product_name]
    except KeyError:
        return jsonify({"error": "Market rate data not found for the given product and category."}), 404

    # Fetch all transactions for the product under the farmer
    transactions = (
        db.session.query(Purchase, Product)
        .join(Product, Purchase.product_id == Product.id)
        .filter(Product.farmer_id == farmer_id)
        .filter(Product.category == category)
        .filter(Product.name == product_name)
        .all()
    )

    # If no transactions found
    if not transactions:
        return jsonify({"error": "No transactions found for the given product and category."}), 404

    # Calculate profit or loss for each transaction
    response = []
    for purchase, product in transactions:
        profit_or_loss = purchase.payment_amount - (market_rate * purchase.quantity)
        response.append({
            "product_name": product.name,
            "category": product.category,
            "market_rate_per_unit": market_rate,
            "sold_price_per_unit": product.price,
            "quantity_sold": purchase.quantity,
            "total_sold_price": purchase.payment_amount,
            "profit_or_loss": profit_or_loss,
            "transaction_date": purchase.created_at.strftime("%Y-%m-%d"),
        })

    return jsonify(response), 200


@app.route("/retailers/<string:retailer_id>/purchase-analysis", methods=["GET"])
def retailer_purchase_analysis(retailer_id):
    retailer = Retailer.query.get(retailer_id)
    if not retailer:
        return jsonify({"error": "Retailer not found"}), 404

    transactions = (
        db.session.query(Purchase, Product, Farmer)
        .join(Product, Purchase.product_id == Product.id)
        .join(Farmer, Product.farmer_id == Farmer.id)
        .filter(Purchase.retailer_id == retailer_id)
        .all()
    )

    if not transactions:
        return jsonify({"error": "No purchases found for this retailer."}), 404

    response = []
    for purchase, product, farmer in transactions:
        state = farmer.State
        category = product.category
        product_name = product.name

        market_rate = None
        try:
            market_rate = market_data[state]["products"][category][product_name]
        except KeyError:
            pass  # Market rate not found for this product/category/state

        purchase_price_per_unit = purchase.payment_amount / purchase.quantity if purchase.quantity > 0 else 0
        market_price_per_unit = market_rate if market_rate is not None else "N/A"
        
        price_difference_per_unit = "N/A"
        if market_rate is not None:
            price_difference_per_unit = purchase_price_per_unit - market_rate

        response.append({
            "order_id": purchase.id,
            "product_name": product.name,
            "category": product.category,
            "farmer_name": farmer.farmername,
            "quantity_bought": purchase.quantity,
            "purchase_price_per_unit": round(purchase_price_per_unit, 2),
            "market_price_per_unit": market_price_per_unit,
            "price_difference_per_unit": round(price_difference_per_unit, 2) if isinstance(price_difference_per_unit, float) else price_difference_per_unit,
            "total_purchase_amount": purchase.payment_amount,
            "purchase_date": purchase.created_at.strftime("%Y-%m-%d"),
        })

    return jsonify(response), 200


if __name__=="__main__":
    app.run(host="0.0.0.0",port=5000,debug=True)


