from decimal import Decimal
from io import BytesIO

from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer


def generate_invoice_pdf(order):
    """Génère une facture PDF pour une commande.

    Args:
        order: Instance de Order

    Returns:
        BytesIO: Le PDF en mémoire
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm,
                           topMargin=2*cm, bottomMargin=2*cm)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#8B5CF6'),
        spaceAfter=30,
    )
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#1F2937'),
        spaceAfter=12,
    )

    elements = []

    # En-tête
    elements.append(Paragraph("Mamy Khaliqa", title_style))
    elements.append(Paragraph(f"Facture N° {order.invoice.number}", heading_style))
    elements.append(Paragraph(f"Date: {order.invoice.issued_at.strftime('%d/%m/%Y')}", styles['Normal']))
    elements.append(Spacer(1, 0.5*cm))

    # Informations client
    elements.append(Paragraph("Informations client", heading_style))
    client_info = f"""
    {order.first_name} {order.last_name}<br/>
    {order.address_line}<br/>
    {order.city}<br/>
    Tél: {order.phone}
    """
    elements.append(Paragraph(client_info, styles['Normal']))
    elements.append(Spacer(1, 0.5*cm))

    # Référence commande
    elements.append(Paragraph("Référence commande", heading_style))
    elements.append(Paragraph(f"Commande N° {order.number}", styles['Normal']))
    elements.append(Spacer(1, 0.5*cm))

    # Tableau des articles
    elements.append(Paragraph("Détail de la commande", heading_style))

    data = [['Article', 'Prix unitaire', 'Quantité', 'Total']]
    for item in order.items.all():
        product_name = item.product_name
        if item.variant_name:
            product_name += f" ({item.variant_name})"
        data.append([
            product_name,
            f"{item.unit_price / 100:.2f} XOF",
            str(item.quantity),
            f"{item.line_total / 100:.2f} XOF"
        ])

    table = Table(data, colWidths=[6*cm, 3*cm, 2*cm, 3*cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#8B5CF6')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 0.5*cm))

    # Totaux
    elements.append(Paragraph("Récapitulatif", heading_style))
    total_data = [
        ['Sous-total', f"{order.subtotal / 100:.2f} XOF"],
        ['Livraison', f"{order.delivery_fee / 100:.2f} XOF"],
        ['TOTAL', f"{order.total / 100:.2f} XOF"],
    ]

    total_table = Table(total_data, colWidths=[8*cm, 4*cm])
    total_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 2), (-1, 2), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 2), (-1, 2), 12),
        ('TEXTCOLOR', (0, 2), (-1, 2), colors.HexColor('#8B5CF6')),
        ('LINEABOVE', (0, 2), (-1, 2), 2, colors.HexColor('#8B5CF6')),
    ]))
    elements.append(total_table)
    elements.append(Spacer(1, 1*cm))

    # Statut paiement
    payment_status = "PAYÉ" if order.payment_status == "paid" else "EN ATTENTE"
    elements.append(Paragraph(f"Statut paiement: {payment_status}", heading_style))

    # Pied de page
    elements.append(Spacer(1, 2*cm))
    footer_text = """
    Merci pour votre commande !<br/><br/>
    Mamy Khaliqa<br/>
    WhatsApp: +221 77 185 71 34<br/>
    Email: mamycama52@gmail.com
    """
    elements.append(Paragraph(footer_text, styles['Normal']))

    doc.build(elements)
    buffer.seek(0)
    return buffer


def send_invoice_email(order, pdf_buffer):
    """Envoie la facture par email au client et à l'admin.

    Args:
        order: Instance de Order
        pdf_buffer: BytesIO contenant le PDF
    """
    # Email au client
    if order.email:
        subject = f"Votre facture Mamy Khaliqa - Commande {order.number}"
        body = f"""
        Bonjour {order.first_name},

        Merci pour votre commande chez Mamy Khaliqa !

        Votre facture est jointe à cet email.

        Référence de commande : {order.number}
        Montant total : {order.total / 100:.2f} XOF

        À très bientôt !

        Mamy Khaliqa
        WhatsApp: +221 77 185 71 34
        Email: mamycama52@gmail.com
        """

        email = EmailMessage(
            subject,
            body,
            settings.DEFAULT_FROM_EMAIL,
            [order.email],
        )
        email.attach(f"Facture_{order.invoice.number}.pdf", pdf_buffer.read(), 'application/pdf')
        email.send()

    # Email à l'admin
    admin_subject = f"Nouvelle facture générée - Commande {order.number}"
    admin_body = f"""
    Une nouvelle facture a été générée pour la commande {order.number}.

    Client: {order.first_name} {order.last_name}
    Email: {order.email or 'Non renseigné'}
    Téléphone: {order.phone}
    Montant: {order.total / 100:.2f} XOF
    Statut paiement: {order.get_payment_status_display()}
    """

    admin_email = EmailMessage(
        admin_subject,
        admin_body,
        settings.DEFAULT_FROM_EMAIL,
        [settings.DEFAULT_FROM_EMAIL],  # Envoyer à l'admin (à configurer)
    )
    admin_email.attach(f"Facture_{order.invoice.number}.pdf", pdf_buffer.read(), 'application/pdf')
    admin_email.send()
