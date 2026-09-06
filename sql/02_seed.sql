INSERT INTO plans (id, name, cpu_cores, ram_mb, disk_mb, price_monthly) VALUES
    ('starter', 'Starter', 1.0, 2048, 10240, 199.00),
    ('plus',    'Plus',    2.0, 4096, 20480, 399.00),
    ('pro',     'Pro',     2.0, 6144, 40960, 699.00)
ON CONFLICT (id) DO NOTHING;
