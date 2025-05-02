from flask import Flask, render_template, request, send_file, jsonify, Response
import pandas as pd
import chardet
import os
import glob
import io
import base64
import uuid
import shutil
import zipfile
from tempfile import NamedTemporaryFile, mkdtemp
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'outputs'
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # 200MB

# Klasörleri oluştur
for folder in [app.config['UPLOAD_FOLDER'], app.config['OUTPUT_FOLDER']]:
    if not os.path.exists(folder):
        os.makedirs(folder)

# Birleştirme işlevi
def merge_files(file_paths):
    df_list = []
    total_items = 0
    processed_files = 0
    failed_files = 0
    file_info = []

    # Her dosyayı oku ve satır sayısını hesapla
    for file_path in file_paths:
        try:
            file_name = os.path.basename(file_path)
            file_extension = os.path.splitext(file_path)[1].lower()
            
            if file_extension == '.csv':
                # CSV dosyasını oku
                df = pd.read_csv(file_path)
            else:  # TXT dosyası
                # Dosyanın karakter kodlamasını tespit et
                with open(file_path, 'rb') as f:
                    content = f.read()
                    result = chardet.detect(content)
                encoding = result['encoding'] if result['encoding'] else 'utf-8'
                
                # TXT dosyasını oku - satır başına bir değer olarak
                with open(file_path, 'r', encoding=encoding, errors='replace') as f:
                    lines = [line.strip() for line in f if line.strip()]
                
                # Dosya adını çıkarıyoruz (uzantısız)
                filename = os.path.splitext(file_name)[0]
                
                # DataFrame'e dönüştür (tek sütun 'item' olarak)
                df = pd.DataFrame(lines, columns=['item'])
                
                # Dosya adını kaynak olarak ekle
                df['source'] = filename
            
            # Sütun sayısını ve içeriğini kontrol et
            if len(df.columns) == 0:
                file_info.append(f"⚠️ {file_name} içinde hiç sütun bulunamadı, atlanıyor.")
                failed_files += 1
                continue
                
            item_count = df.shape[0]
            total_items += item_count
            file_info.append(f"📄 {file_name} içinde {item_count} satır bulundu.")
            df_list.append(df)
            processed_files += 1
        except Exception as e:
            file_info.append(f"⚠️ {file_name} okunamadı: {str(e)}")
            failed_files += 1

    if not df_list:
        return None, file_info

    # Tüm verileri birleştir
    try:
        # Sütun isimlerini kontrol et ve gerekirse düzenle
        for i, df in enumerate(df_list):
            # Eğer sütun isimleri farklıysa, standart isimler kullan
            if 'item' not in df.columns:
                # İlk sütunu 'item' olarak yeniden adlandır
                new_columns = df.columns.tolist()
                new_columns[0] = 'item'
                df.columns = new_columns
                df_list[i] = df
                
        # DataFrame'leri birleştir
        merged_df = pd.concat(df_list, ignore_index=True)
        
        # Birleştirme işlemini özetleyen bilgiler
        file_info.append(f"\n📊 İşlenen dosya sayısı: {processed_files} / {len(file_paths)}")
        file_info.append(f"⚠️ İşlenemeyen dosya sayısı: {failed_files}")
        file_info.append(f"📊 Toplam {total_items} satır bulundu.")
        file_info.append(f"🔗 Birleştirilen satır sayısı: {merged_df.shape[0]}")
        
        return merged_df, file_info
        
    except Exception as e:
        file_info.append(f"❌ Birleştirme işlemi sırasında hata oluştu: {str(e)}")
        return None, file_info


# Dosyayı belirtilen satır sayısına göre bölme işlevi
def split_file(df, rows_per_file, output_folder):
    if df is None or df.empty:
        return []

    total_rows = df.shape[0]
    file_count = (total_rows // rows_per_file) + (1 if total_rows % rows_per_file > 0 else 0)
    
    split_files = []
    
    # Her parçayı dosyaya kaydet
    for i in range(file_count):
        start_idx = i * rows_per_file
        end_idx = min((i + 1) * rows_per_file, total_rows)
        
        part_df = df.iloc[start_idx:end_idx]
        
        # Dosya adı oluştur
        output_filename = f"bolum_{i+1}_satir_{start_idx+1}-{end_idx}.csv"
        output_path = os.path.join(output_folder, output_filename)
        
        # Dosyayı kaydet
        part_df.to_csv(output_path, index=False)
        
        # Bilgileri tut
        split_info = {
            'filename': output_filename,
            'path': output_path,
            'rows': end_idx-start_idx
        }
        split_files.append(split_info)
    
    return split_files


# Zip dosyası oluşturma işlevi
def create_zip_file(files, output_path):
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_info in files:
            zipf.write(file_info['path'], arcname=file_info['filename'])
    
    return output_path


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/merge', methods=['POST'])
def merge():
    if 'files[]' not in request.files:
        return jsonify({'error': 'Dosya yüklenmedi'}), 400
    
    uploaded_files = request.files.getlist('files[]')
    
    # Geçici klasör oluştur
    temp_dir = mkdtemp(dir=app.config['UPLOAD_FOLDER'])
    saved_files = []
    
    # Dosyaları kaydet
    for file in uploaded_files:
        if file.filename:
            filename = secure_filename(file.filename)
            file_path = os.path.join(temp_dir, filename)
            file.save(file_path)
            saved_files.append(file_path)
    
    # Birleştirme işlemi
    merged_df, file_info = merge_files(saved_files)
    
    if merged_df is None:
        # Geçici dosyaları temizle
        shutil.rmtree(temp_dir, ignore_errors=True)
        return jsonify({
            'success': False,
            'info': file_info
        })
    
    # Benzersiz bir klasör oluştur
    output_id = str(uuid.uuid4())
    output_dir = os.path.join(app.config['OUTPUT_FOLDER'], output_id)
    os.makedirs(output_dir, exist_ok=True)
    
    # CSV ve Excel dosyaları oluştur
    csv_path = os.path.join(output_dir, 'mazhar_merged_data.csv')
    excel_path = os.path.join(output_dir, 'mazhar_merged_data.xlsx')
    
    merged_df.to_csv(csv_path, index=False)
    merged_df.to_excel(excel_path, index=False)
    
    # Önizleme verileri oluştur
    preview_data = merged_df.head(10).to_dict('records')
    
    # Geçici dosyaları temizle
    shutil.rmtree(temp_dir, ignore_errors=True)
    
    return jsonify({
        'success': True,
        'info': file_info,
        'output_id': output_id,
        'total_rows': merged_df.shape[0],
        'preview': preview_data,
        'columns': merged_df.columns.tolist()
    })


@app.route('/split', methods=['POST'])
def split():
    try:
        data = request.get_json()
        output_id = data.get('output_id')
        rows_per_file = int(data.get('rows_per_file', 1000))
        file_format = data.get('format', 'csv')
        
        # Kaynak dosyayı bul
        source_dir = os.path.join(app.config['OUTPUT_FOLDER'], output_id)
        source_file = os.path.join(source_dir, f'mazhar_merged_data.{file_format}')
        
        if not os.path.exists(source_file):
            return jsonify({'error': 'Dosya bulunamadı'}), 404
        
        # Dosyayı oku
        if file_format == 'csv':
            df = pd.read_csv(source_file)
        else:
            df = pd.read_excel(source_file)
        
        # Bölünmüş dosyalar için klasör
        split_dir = os.path.join(source_dir, 'split')
        os.makedirs(split_dir, exist_ok=True)
        
        # Bölme işlemi
        split_files = split_file(df, rows_per_file, split_dir)
        
        # Zip dosyası oluştur
        zip_filename = 'bolunmus_dosyalar.zip'
        zip_path = os.path.join(source_dir, zip_filename)
        create_zip_file(split_files, zip_path)
        
        return jsonify({
            'success': True,
            'total_files': len(split_files),
            'output_id': output_id,
            'zip_filename': zip_filename,
            'files': [
                {
                    'filename': info['filename'],
                    'rows': info['rows']
                } for info in split_files
            ]
        })
        
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500


@app.route('/download/<output_id>/<path:filename>')
def download_file(output_id, filename):
    if '..' in filename or filename.startswith('/'):
        return "Geçersiz dosya adı", 400
    
    directory = os.path.join(app.config['OUTPUT_FOLDER'], output_id)
    
    if filename == 'mazhar_merged_data.csv' or filename == 'mazhar_merged_data.xlsx' or filename == 'bolunmus_dosyalar.zip':
        file_path = os.path.join(directory, filename)
    elif filename.startswith('split/'):
        # split/ önekini kaldır
        file_path = os.path.join(directory, filename)
    else:
        file_path = os.path.join(directory, 'split', filename)
    
    if not os.path.exists(file_path):
        return "Dosya bulunamadı", 404
        
    return send_file(file_path, as_attachment=True)


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'Dosya yüklenmedi'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'Dosya seçilmedi'}), 400
    
    # Geçici klasör oluştur
    output_id = str(uuid.uuid4())
    output_dir = os.path.join(app.config['OUTPUT_FOLDER'], output_id)
    os.makedirs(output_dir, exist_ok=True)
    
    # Dosyayı kaydet
    filename = secure_filename(file.filename)
    file_path = os.path.join(output_dir, filename)
    file.save(file_path)
    
    # Dosyayı oku
    try:
        if filename.endswith('.csv'):
            df = pd.read_csv(file_path)
        elif filename.endswith('.xlsx') or filename.endswith('.xls'):
            df = pd.read_excel(file_path)
        else:
            return jsonify({'error': 'Desteklenmeyen dosya formatı'}), 400
        
        # CSV olarak kaydet (bölme işlemi için)
        csv_path = os.path.join(output_dir, 'mazhar_merged_data.csv')
        df.to_csv(csv_path, index=False)
        
        # Önizleme verileri oluştur
        preview_data = df.head(5).to_dict('records')
        
        return jsonify({
            'success': True,
            'output_id': output_id,
            'filename': filename,
            'total_rows': df.shape[0],
            'columns': df.columns.tolist(),
            'preview': preview_data
        })
        
    except Exception as e:
        # Hata durumunda temizlik
        shutil.rmtree(output_dir, ignore_errors=True)
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True) 