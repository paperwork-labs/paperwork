import OrderModal from './OrderModal';
import type { OrderModalProps } from './OrderModal';

type SellOrderModalProps = Omit<OrderModalProps, 'side'>;

export default function SellOrderModal(props: SellOrderModalProps) {
  return <OrderModal {...props} side="sell" />;
}
