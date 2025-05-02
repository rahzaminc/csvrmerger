import pandas as pd
import glob
import os
import chardet
import re

# Dosyaların olduğu klasör
data_folder = "csvs"

# Birleştirme fonksiyonu
def merge_files():
    # Klasör yoksa uyarı ver
    if not os.path.exists(data_folder):
        print(f"❌ '{data_folder}' klasörü bulunamadı. Lütfen CSV ve TXT dosyalarını bu klasöre koy.")
        return None

    # Klasör içindeki CSV ve TXT dosyalarını bul
    csv_files = glob.glob(os.path.join(data_folder, "*.csv"))
    txt_files = glob.glob(os.path.join(data_folder, "*.txt"))

    all_files = csv_files + txt_files

    if not all_files:
        print(f"❌ '{data_folder}' klasöründe hiç CSV veya TXT dosyası bulunamadı.")
        return None

    df_list = []
    total_items = 0
    processed_files = 0
    failed_files = 0

    print(f"🔍 Toplam {len(csv_files)} CSV ve {len(txt_files)} TXT dosyası bulundu. İşlem başlatılıyor...\n")

    # Her dosyayı oku ve satır sayısını hesapla
    for file in all_files:
        try:
            if file.endswith('.csv'):
                # CSV dosyasını oku
                df = pd.read_csv(file)
            else:  # TXT dosyası
                # Dosyanın karakter kodlamasını tespit et
                with open(file, 'rb') as f:
                    result = chardet.detect(f.read())
                encoding = result['encoding'] if result['encoding'] else 'utf-8'
                
                # TXT dosyasını oku - satır başına bir değer olarak
                with open(file, 'r', encoding=encoding, errors='replace') as f:
                    lines = [line.strip() for line in f if line.strip()]
                
                # Dosya adını çıkarıyoruz (uzantısız)
                filename = os.path.splitext(os.path.basename(file))[0]
                
                # DataFrame'e dönüştür (tek sütun 'item' olarak)
                df = pd.DataFrame(lines, columns=['item'])
                
                # Dosya adını kaynak olarak ekle
                df['source'] = filename
            
            # Sütun sayısını ve içeriğini kontrol et
            if len(df.columns) == 0:
                print(f"⚠️ {os.path.basename(file)} içinde hiç sütun bulunamadı, atlanıyor.")
                failed_files += 1
                continue
                
            item_count = df.shape[0]
            total_items += item_count
            print(f"📄 {os.path.basename(file)} içinde {item_count} satır bulundu.")
            df_list.append(df)
            processed_files += 1
        except Exception as e:
            print(f"⚠️ {os.path.basename(file)} okunamadı: {e}")
            failed_files += 1

    if not df_list:
        print("❌ Hiçbir dosya okunamadı. Lütfen dosyaların formatını kontrol edin.")
        return None

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
        print(f"\n📊 İşlenen dosya sayısı: {processed_files} / {len(all_files)}")
        print(f"⚠️ İşlenemeyen dosya sayısı: {failed_files}")
        print(f"📊 Toplam {total_items} satır bulundu.")
        print(f"🔗 Birleştirilen satır sayısı: {merged_df.shape[0]}")
        
        return merged_df
        
    except Exception as e:
        print(f"❌ Birleştirme işlemi sırasında hata oluştu: {e}")
        return None

# Dosyayı belirtilen satır sayısına göre bölme fonksiyonu
def split_file(df, rows_per_file):
    if df is None or df.empty:
        print("❌ Bölünecek dosya bulunamadı veya boş.")
        return False
    
    total_rows = df.shape[0]
    file_count = (total_rows // rows_per_file) + (1 if total_rows % rows_per_file > 0 else 0)
    
    print(f"\n✂️ Dosya {file_count} parçaya bölünüyor...")
    
    # Klasör oluştur
    output_folder = "bolunmus_dosyalar"
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    # Her parçayı dosyaya kaydet
    for i in range(file_count):
        start_idx = i * rows_per_file
        end_idx = min((i + 1) * rows_per_file, total_rows)
        
        part_df = df.iloc[start_idx:end_idx]
        
        # Dosya adı oluştur
        output_file = os.path.join(output_folder, f"bolum_{i+1}_satir_{start_idx+1}-{end_idx}.csv")
        
        # Dosyayı kaydet
        part_df.to_csv(output_file, index=False)
        print(f"📄 Parça {i+1}/{file_count} kaydedildi: {output_file} ({end_idx-start_idx} satır)")
    
    print(f"\n✅ Bölme işlemi tamamlandı! Dosyalar '{output_folder}' klasörüne kaydedildi.")
    return True

# Ana menü
def main_menu():
    while True:
        print("\n📋 CSV ve TXT İşleme Aracı 📋")
        print("1 - Dosyaları Birleştir")
        print("2 - Dosyayı Böl")
        print("3 - Çıkış")
        
        choice = input("\nSeçiminiz (1-3): ")
        
        if choice == "1":
            # Dosyaları birleştir
            merged_df = merge_files()
            
            if merged_df is not None:
                # Kullanıcıya çıktı formatını sor
                print("\n💾 Hangi formatta çıktı almak istiyorsun?")
                print("1 - CSV (.csv)")
                print("2 - Excel (.xlsx)")
                format_choice = input("Seçimin (1 ya da 2): ")
                
                # Çıktıyı ana dizine yaz
                if format_choice == "2":
                    output_file = "mazhar_merged_data.xlsx"
                    merged_df.to_excel(output_file, index=False)
                else:
                    output_file = "mazhar_merged_data.csv"
                    merged_df.to_csv(output_file, index=False)
                
                print(f"\n✅ Dosya başarıyla oluşturuldu: {output_file}")
                
                # Bölme seçeneği sor
                print("\n✂️ Birleştirilen dosyayı bölmek ister misin?")
                print("1 - Evet")
                print("2 - Hayır")
                split_choice = input("Seçimin (1 ya da 2): ")
                
                if split_choice == "1":
                    # Bölme işlemi için satır sayısını sor
                    split_rows = split_menu()
                    if split_rows:
                        split_file(merged_df, split_rows)
            
        elif choice == "2":
            # Dosya seç ve böl
            print("\n📂 Bölmek istediğiniz dosyayı seçin:")
            
            # Ana dizindeki CSV ve Excel dosyalarını listele
            csv_files = glob.glob("*.csv")
            excel_files = glob.glob("*.xlsx")
            all_files = csv_files + excel_files
            
            if not all_files:
                print("❌ Bölünecek dosya bulunamadı. Önce dosya oluşturun veya ana dizine bir dosya ekleyin.")
                continue
            
            for idx, file in enumerate(all_files, 1):
                print(f"{idx} - {file}")
            
            file_idx = input(f"Dosya numarası (1-{len(all_files)}): ")
            try:
                file_idx = int(file_idx) - 1
                if file_idx < 0 or file_idx >= len(all_files):
                    print("❌ Geçersiz dosya numarası!")
                    continue
                
                file_path = all_files[file_idx]
                
                # Dosyayı oku
                if file_path.endswith('.csv'):
                    df = pd.read_csv(file_path)
                else:
                    df = pd.read_excel(file_path)
                
                print(f"\n📊 Seçilen dosya: {file_path} ({df.shape[0]} satır, {df.shape[1]} sütun)")
                
                # Bölme işlemi için satır sayısını sor
                split_rows = split_menu()
                if split_rows:
                    split_file(df, split_rows)
                
            except (ValueError, Exception) as e:
                print(f"❌ Hata: {e}")
                
        elif choice == "3":
            print("\n👋 Program sonlandırılıyor. İyi günler!")
            break
            
        else:
            print("❌ Geçersiz seçim! Lütfen 1-3 arasında bir değer girin.")

# Bölme seçenekleri menüsü
def split_menu():
    print("\n🔢 Kaç satırda bir bölmek istiyorsunuz?")
    print("1 - 1.000 satır")
    print("2 - 5.000 satır")
    print("3 - 10.000 satır")
    print("4 - 20.000 satır")
    print("5 - Özel değer")
    print("6 - İptal")
    
    choice = input("Seçiminiz (1-6): ")
    
    rows_per_file = 0
    
    if choice == "1":
        rows_per_file = 1000
    elif choice == "2":
        rows_per_file = 5000
    elif choice == "3":
        rows_per_file = 10000
    elif choice == "4":
        rows_per_file = 20000
    elif choice == "5":
        try:
            rows_per_file = int(input("Satır sayısı: "))
            if rows_per_file <= 0:
                print("❌ Geçersiz satır sayısı! Pozitif bir değer girmelisiniz.")
                return 0
        except ValueError:
            print("❌ Geçersiz değer! Sayısal bir değer girmelisiniz.")
            return 0
    elif choice == "6":
        return 0
    else:
        print("❌ Geçersiz seçim!")
        return 0
    
    return rows_per_file

# Programı başlat
if __name__ == "__main__":
    main_menu()